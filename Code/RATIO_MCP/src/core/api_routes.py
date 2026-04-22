"""Config-driven REST API route registrations.

Replaces per-tool endpoint boilerplate with a generic dispatcher.
Tool endpoints are auto-generated from tools_config.json via the tool registry.
Prompt and resource listing/content endpoints remain generic.
"""
from __future__ import annotations
import json as _json
import inspect
from typing import Any
from core.mcp_app import logger, mcpserver
from core.job_manager import schedule_tool_job, get_job, list_jobs, cancel_job
from core.call_tracker import start_call, finish_call, list_calls
import registry.tools as tools
from registry.tools import user_token_var
import registry.prompts as prompts
import registry.resources as resources
from helper.mcp_logger import MCPLogger, get_current_xcv, generate_xcv

try:
    from starlette.responses import JSONResponse
    from starlette.routing import Route
except Exception as e:  # pragma: no cover
    logger.warning("Starlette unavailable; API routes disabled: %s", e)
    JSONResponse = None  # type: ignore
    Route = None  # type: ignore


# ---------------------------------------------------------------------------
# Generic tool dispatcher — replaces all per-tool endpoint functions
# ---------------------------------------------------------------------------

async def _generic_tool_endpoint(request):
    """Invoke any registered tool by name via POST /api/tools/{tool_name}.

    Body: JSON object whose keys match the tool's parameters.
    Optional: {"async": true} triggers background job execution (returns 202).

    If the request carries an Authorization header, the bearer token is
    forwarded to tool handlers via the user_token_var context variable.
    Every call is recorded by call_tracker for audit/logging.
    """
    try:
        tool_name = request.path_params.get("tool_name")
        if not tool_name:
            return JSONResponse({"error": "Missing tool_name path parameter."}, status_code=400)

        handler = tools.get_tool_handler(tool_name)
        if handler is None:
            return JSONResponse({"error": f"Unknown tool '{tool_name}'"}, status_code=404)

        # Extract bearer token from Authorization header (if present)
        auth_header = request.headers.get("authorization", "")
        bearer_token = None
        if auth_header.lower().startswith("bearer "):
            bearer_token = auth_header[7:].strip()

        data = await request.json()
        async_flag = data.pop("async", False) or request.query_params.get("async") in ("1", "true", "yes")

        # Caller info for call tracking
        caller_ip = request.client.host if request.client else None
        auth_claims = request.scope.get("auth_claims", {})
        caller_sub = auth_claims.get("sub") or auth_claims.get("azp") or auth_claims.get("appid")

        # ── MCP Logger ──
        xcv = get_current_xcv() or generate_xcv()
        mcp_log = MCPLogger.get_instance()
        mode = "async" if async_flag else "sync"

        if async_flag:
            call_rec = await start_call(tool_name, data, caller_ip=caller_ip, caller_sub=caller_sub, mode="async")
            mcp_log.log_tool_call_start(xcv, tool_name, data, mode="async")
            job = await schedule_tool_job(tool_name, handler, data)
            await finish_call(call_rec["id"], result=f"job_id={job['id']}")
            mcp_log.log_tool_call_end(xcv, tool_name, result=f"job_id={job['id']}")
            return JSONResponse({"job_id": job["id"], "status": job["status"], "tool": job["tool_name"]}, status_code=202)

        # Track the synchronous call
        call_rec = await start_call(tool_name, data, caller_ip=caller_ip, caller_sub=caller_sub, mode="sync")
        mcp_log.log_tool_call_start(xcv, tool_name, data, mode="sync")

        # Set the user token context var so handlers can access it
        import time as _time
        _t0 = _time.monotonic()
        token_reset = user_token_var.set(bearer_token)
        try:
            raw = await handler(**data)
            elapsed = (_time.monotonic() - _t0) * 1000
            await finish_call(call_rec["id"], result=raw)
            mcp_log.log_tool_call_end(xcv, tool_name, result=raw, duration_ms=elapsed)
        except Exception as handler_err:
            elapsed = (_time.monotonic() - _t0) * 1000
            await finish_call(call_rec["id"], error=str(handler_err))
            mcp_log.log_tool_call_end(xcv, tool_name, error=str(handler_err), duration_ms=elapsed)
            raise
        finally:
            user_token_var.reset(token_reset)

        try:
            parsed = _json.loads(raw)
            return JSONResponse(parsed)
        except (TypeError, _json.JSONDecodeError):
            return JSONResponse({"result": raw})
    except Exception as e:
        logger.error("generic_tool_endpoint failed for %s: %s", request.path_params.get("tool_name"), e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Call tracking endpoints
# ---------------------------------------------------------------------------

async def _list_calls_endpoint(request):
    """Return recent call records for audit/logging.

    Optional query params:
      ?tool=<name>   — filter by tool name
      ?status=<s>    — filter by status (running|succeeded|failed|cancelled)
      ?limit=<n>     — max records to return (default 100)
    """
    try:
        all_calls = await list_calls()
        tool_filter = request.query_params.get("tool")
        status_filter = request.query_params.get("status")
        limit = int(request.query_params.get("limit", "100"))

        filtered = all_calls
        if tool_filter:
            filtered = [c for c in filtered if c["tool_name"] == tool_filter]
        if status_filter:
            filtered = [c for c in filtered if c["status"] == status_filter]

        # Most recent first
        filtered.sort(key=lambda c: c.get("started_at", 0), reverse=True)
        filtered = filtered[:limit]

        return JSONResponse({"calls": filtered, "count": len(filtered)})
    except Exception as e:
        logger.error("list_calls endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Job management endpoints (unchanged)
# ---------------------------------------------------------------------------

async def _submit_job_endpoint(request):
    """Generic job submission for any registered tool by name.

    Body: {"tool": "run_tsql_query_tool", "params": {...}}
    Returns 202 with job id.
    """
    try:
        data = await request.json()
        tool_name = data.get("tool")
        params = data.get("params") or {}
        if not isinstance(tool_name, str):
            return JSONResponse({"error": "tool must be a string"}, status_code=400)
        if not isinstance(params, dict):
            return JSONResponse({"error": "params must be an object"}, status_code=400)
        handler = tools.get_tool_handler(tool_name)
        if handler is None:
            return JSONResponse({"error": f"Unknown tool '{tool_name}'"}, status_code=404)
        job = await schedule_tool_job(tool_name, handler, params)
        return JSONResponse({"job_id": job["id"], "status": job["status"], "tool": job["tool_name"]}, status_code=202)
    except Exception as e:
        logger.error("submit_job endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def _job_status_endpoint(request):
    job_id = request.path_params.get("job_id") if hasattr(request, "path_params") else None
    if not isinstance(job_id, str):
        return JSONResponse({"error": "Missing job_id path parameter"}, status_code=400)
    job = await get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    decoded = None
    res = job.get("result")
    if isinstance(res, str):
        try:
            decoded = _json.loads(res)
        except Exception:
            pass
    return JSONResponse({
        "id": job["id"],
        "status": job["status"],
        "tool": job["tool_name"],
        "error": job.get("error"),
        "result": decoded if decoded is not None else res,
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    })


async def _list_jobs_endpoint(_request):
    jobs = await list_jobs()
    brief = [{"id": j["id"], "status": j["status"], "tool": j["tool_name"], "finished_at": j.get("finished_at")} for j in jobs]
    return JSONResponse({"jobs": brief, "count": len(brief)})


async def _job_cancel_endpoint(request):
    job_id = request.path_params.get("job_id") if hasattr(request, "path_params") else None
    if not isinstance(job_id, str):
        return JSONResponse({"error": "Missing job_id path parameter"}, status_code=400)
    ok = await cancel_job(job_id)
    if not ok:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    job = await get_job(job_id)
    return JSONResponse({"id": job_id, "status": job.get("status") if job else "cancelled"})


# ---------------------------------------------------------------------------
# Listing endpoints (config-driven)
# ---------------------------------------------------------------------------

async def _list_tools_endpoint(_request):
    """Return dynamic list of MCP tools registered via config."""
    try:
        tool_entries: list[dict[str, Any]] = []
        for name in tools.get_all_tool_names():
            func = tools.get_tool_handler(name)
            if not func:
                continue
            doc = (getattr(func, "__doc__", None) or "").strip() or None
            params = []
            returns = None
            try:
                sig = inspect.signature(func)
                for p in sig.parameters.values():
                    ann = p.annotation if p.annotation is not inspect._empty else None
                    ptype = getattr(ann, "__name__", None) or str(ann) if ann else None
                    default = None if p.default is inspect._empty else p.default
                    params.append({"name": p.name, "type": ptype, "default": default})
                if sig.return_annotation is not inspect._empty:
                    returns = getattr(sig.return_annotation, "__name__", None) or str(sig.return_annotation)
            except Exception:
                pass
            returns_doc = None
            if doc:
                for line in doc.splitlines():
                    if line.lower().startswith("returns:"):
                        returns_doc = line.partition(":")[2].strip()
                        break
            tool_entries.append({
                "name": name,
                "doc": doc,
                "params": params,
                "returns": returns_doc or returns
            })
        return JSONResponse({"tools": tool_entries, "count": len(tool_entries)})
    except Exception as e:
        logger.error("list_tools endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def _list_prompts_endpoint(_request):
    """List registered prompts with docstring."""
    try:
        entries = []
        # Use the config-driven registered names from prompts module
        names = getattr(prompts, "_registered_names", [])
        if not names:
            exported = getattr(prompts, "__all__", [])
            names = list(exported) if isinstance(exported, (list, tuple)) else []

        # Get prompt descriptions from config
        try:
            config_entries = prompts._load_prompt_config()
            desc_map = {e["name"]: e.get("description", "") for e in config_entries}
        except Exception:
            desc_map = {}

        for name in names:
            doc = desc_map.get(name, "")
            entries.append({"name": name, "doc": doc})
        return JSONResponse({"prompts": entries, "count": len(entries)})
    except Exception as e:
        logger.error("list_prompts endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def _list_resources_endpoint(_request):
    """List registered resources with metadata."""
    try:
        entries: list[dict[str, Any]] = []

        # Use config to build metadata
        try:
            config_entries = resources._load_resource_config()
        except Exception:
            config_entries = []

        for entry in config_entries:
            meta = {
                "name": entry.get("name"),
                "uri": entry.get("uri"),
                "title": entry.get("title"),
                "description": entry.get("description"),
                "mime_type": entry.get("mime_type"),
            }
            entries.append({"name": entry["name"], "meta": meta, "dataset_size": None})

        # Fallback: try FastMCP internal registry
        if not entries:
            registry = getattr(mcpserver, "_resources", None)
            if isinstance(registry, dict) and registry:
                for rname, robj in registry.items():
                    meta = {}
                    for attr in ("title", "description", "mime_type", "name", "uri"):
                        val = getattr(robj, attr, None)
                        if val:
                            meta[attr] = str(val) if not isinstance(val, (str, int, float, bool)) else val
                    entries.append({"name": str(rname), "meta": meta, "dataset_size": None})

        return JSONResponse({"resources": entries, "count": len(entries)})
    except Exception as e:
        logger.error("list_resources endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def _prompt_content_endpoint(request):
    """Return full prompt content for provided prompt name via GET path parameter."""
    try:
        name = request.path_params.get("name") if hasattr(request, "path_params") else None
        if not isinstance(name, str) or not name.strip():
            return JSONResponse({"error": "Missing prompt name path parameter."}, status_code=400)
        try:
            full_text = prompts._compose_prompt(name)
        except ValueError:
            return JSONResponse({"error": f"Unknown prompt name '{name}'"}, status_code=404)
        # ── MCP Logger ──
        xcv = get_current_xcv() or generate_xcv()
        MCPLogger.get_instance().log_prompt_served(xcv, name, length=len(full_text))
        return JSONResponse({"name": name, "length": len(full_text), "text": full_text})
    except Exception as e:
        logger.error("prompt_content endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


async def _resource_content_endpoint(request):
    """Return full dataset for provided resource name via GET path parameter."""
    try:
        name = request.path_params.get("name") if hasattr(request, "path_params") else None
        if not isinstance(name, str) or not name.strip():
            return JSONResponse({"error": "Missing resource name path parameter."}, status_code=400)

        # Look up resource loader from config
        config_entries = resources._load_resource_config()
        entry = next((e for e in config_entries if e["name"] == name), None)
        if entry is None:
            return JSONResponse({"error": f"Unknown resource name '{name}'"}, status_code=404)

        # Load the data
        if entry.get("type", "json") == "json":
            content = resources._load_json_dataset(entry["filename"])
        else:
            content = resources._load_text_dataset(entry["filename"])

        meta = {
            "name": entry.get("name"),
            "uri": entry.get("uri"),
            "title": entry.get("title"),
            "description": entry.get("description"),
            "mime_type": entry.get("mime_type"),
        }
        try:
            length = len(_json.dumps(content))
        except Exception:
            length = 0
        # ── MCP Logger ──
        xcv = get_current_xcv() or generate_xcv()
        MCPLogger.get_instance().log_resource_served(xcv, name, source="api")
        return JSONResponse({"name": name, "length": length, "content": content, "meta": meta})
    except Exception as e:
        logger.error("resource_content endpoint failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# OpenAPI spec & docs (auto-generated from config)
# ---------------------------------------------------------------------------

def _build_openapi_spec() -> dict:
    """Build OpenAPI spec dynamically from tools_config.json."""
    paths: dict[str, Any] = {}

    # Generic tool endpoint
    paths["/api/tools/{tool_name}"] = {
        "post": {
            "summary": "Invoke any registered tool by name",
            "parameters": [
                {"name": "tool_name", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}}
            },
            "responses": {
                "200": {"description": "Tool result"},
                "202": {"description": "Job submitted (async mode)"},
                "400": {"description": "Validation error"},
                "404": {"description": "Unknown tool"},
                "500": {"description": "Server error"}
            }
        }
    }

    # Per-tool entries in OpenAPI (all via generic dispatcher)
    try:
        config_entries = tools._load_tools_config()
        for entry in config_entries:
            tool_name = entry["name"]
            props = {}
            required = []
            for pname, pspec in entry.get("parameters", {}).items():
                ptype = pspec.get("type", "string")
                if ptype == "object":
                    props[pname] = {"type": "object"}
                elif ptype == "integer":
                    props[pname] = {"type": "integer"}
                else:
                    props[pname] = {"type": "string"}
                if pspec.get("description"):
                    props[pname]["description"] = pspec["description"]
                if pspec.get("required"):
                    required.append(pname)
    except Exception as e:
        logger.debug("Could not build per-tool OpenAPI paths: %s", e)

    # Standard endpoints
    paths["/api/tools"] = {"get": {"summary": "List registered tools", "responses": {"200": {"description": "Tool list"}}}}
    paths["/api/prompts"] = {"get": {"summary": "List registered prompts", "responses": {"200": {"description": "Prompt list"}}}}
    paths["/api/resources"] = {"get": {"summary": "List registered resources", "responses": {"200": {"description": "Resource list"}}}}
    paths["/api/prompt_content/{name}"] = {"get": {"summary": "Fetch full prompt content by name", "parameters": [{"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Prompt content"}, "404": {"description": "Unknown prompt"}}}}
    paths["/api/resource_content/{name}"] = {"get": {"summary": "Fetch full resource content by name", "parameters": [{"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Resource content"}, "404": {"description": "Unknown resource"}}}}
    paths["/health"] = {"get": {"summary": "Health check", "responses": {"200": {"description": "OK"}}}}

    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Ratio MCP Server REST API",
            "version": "2.0.0",
            "description": "Config-driven REST endpoints alongside MCP protocol (/mcp)."
        },
        "paths": paths
    }


async def _openapi_doc(_request):
    return JSONResponse(_build_openapi_spec())


async def _human_docs(_request):
    lines = [
        "# Ratio MCP REST API\n",
        "## Generic Tool Endpoint\n",
        "### POST /api/tools/{tool_name}\n",
        "Invoke any registered tool by name. Body is a JSON object with tool parameters.\n",
        "Add `{\"async\": true}` to body for background execution (returns 202 with job_id).\n",
        "```powershell",
        "$body = @{ query='SELECT TOP 5 * FROM MyTable'; max_rows=5 } | ConvertTo-Json",
        "Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/tools/run_tsql_query_tool -Body $body -ContentType 'application/json'",
        "```\n",
    ]

    # Auto-document tools
    try:
        config_entries = tools._load_tools_config()
        lines.append("## Available Tools\n")
        lines.append("All tools are invoked via `POST /api/tools/{tool_name}`.\n")
        for entry in config_entries:
            tool_name = entry["name"]
            desc_line = entry.get("description", "").split("\n")[0]
            lines.append(f"### {tool_name}\n")
            lines.append(f"{desc_line}\n")
    except Exception:
        pass

    lines.extend([
        "\n## Listing Endpoints\n",
        "### GET /api/tools — List registered tools\n",
        "### GET /api/prompts — List registered prompts\n",
        "### GET /api/resources — List registered resources\n",
        "### GET /api/prompt_content/{name} — Fetch full prompt text\n",
        "### GET /api/resource_content/{name} — Fetch full resource data\n",
        "\n## Job Management\n",
        "### POST /api/jobs — Submit async job\n",
        "### GET /api/jobs — List all jobs\n",
        "### GET /api/jobs/{job_id} — Job status\n",
        "### DELETE /api/jobs/{job_id} — Cancel job\n",
        "\n### GET /api/openapi — Machine-readable OpenAPI spec\n",
        "### GET /health — Health check\n",
    ])

    return JSONResponse({"markdown": "\n".join(lines)})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_api_routes(app):
    """Attach REST API routes to the ASGI app."""
    if JSONResponse is None or Route is None:
        logger.warning("Starlette unavailable; skipping custom API route registration.")
        return

    # Generic tool dispatcher
    app.routes.append(Route("/api/tools/{tool_name}", _generic_tool_endpoint, methods=["POST"]))

    # Call tracking
    app.routes.append(Route("/api/calls", _list_calls_endpoint, methods=["GET"]))

    # Listing & content endpoints
    app.routes.append(Route("/api/tools", _list_tools_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/prompts", _list_prompts_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/resources", _list_resources_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/prompt_content/{name}", _prompt_content_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/resource_content/{name}", _resource_content_endpoint, methods=["GET"]))

    # OpenAPI & docs
    app.routes.append(Route("/api/openapi", _openapi_doc, methods=["GET"]))
    app.routes.append(Route("/api/docs", _human_docs, methods=["GET"]))

    # Job management
    app.routes.append(Route("/api/jobs", _submit_job_endpoint, methods=["POST"]))
    app.routes.append(Route("/api/jobs", _list_jobs_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/jobs/{job_id}", _job_status_endpoint, methods=["GET"]))
    app.routes.append(Route("/api/jobs/{job_id}", _job_cancel_endpoint, methods=["DELETE"]))


__all__ = ["register_api_routes"]
