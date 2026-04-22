"""MCP client for invoking tools or fetching prompts using stdio or streamable-http transports.

Usage examples (local stdio):
  python -m src.mcp_client --list
  python -m src.mcp_client build_airod_analyst_prompt
  python -m src.mcp_client --prompt airod_analyst

Usage examples (remote streamable-http):
  python -m src.mcp_client --url http://localhost:3000 --list
  python -m src.mcp_client --url http://localhost:3000 build_airod_analyst_prompt
  python -m src.mcp_client --url http://localhost:3000 --prompt airod_analyst

Transport selection: --transport auto|stdio|streamable-http (default auto).
If --url provided and transport=auto, streamable-http is used.

Environment variables:
  MCP_PYTHON       Python interpreter for local spawn.
  MCP_SERVER_ENTRY Module path for server entry (default __init__).
  MCP_SERVER_URL   Remote base URL (implies streamable-http when transport=auto).
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()
import argparse
import asyncio
import logging
import os
import json
import time
import urllib.request
import urllib.parse
import sys
from typing import Any, Dict, List, Optional, Sequence
try:  
    from mcp.client import Client  # type: ignore
    client = Client("http://127.0.0.1:8000/mcp")  # example instance (not used directly)
    _HAS_UNIFIED_CLIENT = True
except ImportError:
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore
    from mcp import ClientSession  # type: ignore
    Client = None  # sentinel
    _HAS_UNIFIED_CLIENT = False
    _HAS_HTTP_CLIENT = False

DEFAULT_TOOL = "build_airod_analyst_prompt"

logger = logging.getLogger("mcp_client")
if not logger.handlers:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")


def _normalize_url() -> str:
    raw = os.environ.get("MCP_SERVER_URL") or "http://127.0.0.1:8000"
    return raw.rstrip("/") + ("/mcp" if not raw.rstrip("/").endswith("mcp") else "")

IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2019-11-01&resource={aud}"  # resource style
IMDS_SCOPE_URL = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2019-11-01&scope={scope}"  # scope style

def _get_bearer_token(audience: str | None) -> str | None:
    """Return bearer token from MCP_BEARER_TOKEN env or Managed Identity IMDS.

    Env precedence:
      MCP_BEARER_TOKEN (direct token)
      MCP_BEARER_TOKEN_FILE (path to file with token)

    If absent and audience provided (MCP_AUDIENCE), attempt IMDS fetch.
    Supports both resource=api://client-id and scope=api://client-id/.default forms.
    """
    # Always generate a fresh token via IMDS; ignore any pre-provided env/file token.
    aud = audience or os.getenv("MCP_AUTH_AUDIENCE")
    print(os.getenv("MCP_AUTH_AUDIENCE"))
    if not aud:
        print("[mcp_client] MCP_AUTH_AUDIENCE missing; no token generated")
        return None
    # Try scope form first (.default)
    scope = f"{aud}/.default" if not aud.endswith("/.default") else aud
    for url in (IMDS_SCOPE_URL.format(scope=urllib.parse.quote(scope, safe="")), IMDS_URL.format(aud=urllib.parse.quote(aud, safe=""))):
        try:
            req = urllib.request.Request(url, headers={"Metadata": "true"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                token = data.get("access_token")
                if token:
                    print(f"[mcp_client] Generated managed identity token: {token}")
                    return token
        except Exception as e:
            logger.debug("IMDS token attempt failed for %s: %s", url, e)
    print("[mcp_client] Failed to acquire managed identity token from IMDS")
    return None


async def list_available_tools(client) -> List[str]:
    response = await client.list_tools()
    available: List[str] = []
    for item in response:
        if isinstance(item, tuple) and item and item[0] == "tools":
            available.extend([t.name for t in item[1]])
        else:
            try:
                available.append(item.name)  
            except AttributeError:
                pass
    return available

async def list_available_prompts(client) -> List[str]:
    response = await client.list_prompts()
    logger.debug("Raw list_prompts response: %r", response)
    prompts: List[str] = []
    for item in response:
        if isinstance(item, tuple) and item and item[0] == "prompts":
            prompts.extend([p.name for p in item[1]])
        else:
            try:
                prompts.append(item.name)  
            except AttributeError:
                pass
    return prompts

async def list_available_resources(client) -> List[str]:
    """Return list of resource URIs registered on the MCP server as plain strings."""
    resources: List[str] = []
    try:
        response = await client.list_resources()
        for item in response:
            if isinstance(item, tuple) and item and item[0] == "resources":
                for r in item[1]:
                    uri = getattr(r, "uri", None)
                    if uri is not None:
                        resources.append(str(uri))
            else:
                uri = getattr(item, "uri", None)
                if uri is not None:
                    resources.append(str(uri))
    except Exception as exc:  # pragma: no cover
        logger.error("list_resources failed: %s", exc)
    return resources

def extract_texts(result: object) -> List[str]:
    """Return list of text chunks from FastMCP result object."""
    if isinstance(result, dict) and "content" in result:
        content = result["content"]
    else:
        content = getattr(result, "content", [])
    texts: List[str] = []
    for c in content:
        try:
            if getattr(c, "type", None) == "text":
                texts.append(getattr(c, "text", ""))
        except Exception: 
            pass
    return texts

def run_tool(tool_name: str, tool_args: Optional[Dict[str, Any]] = None) -> List[str]:
    """Invoke a tool synchronously and return list of text chunks.

    URL is derived from MCP_SERVER_URL env; '/mcp' appended if missing.
    """
    async def _runner() -> List[str]:
        target = _normalize_url()
        token = _get_bearer_token(None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if _HAS_UNIFIED_CLIENT:
            async with Client(target, headers=headers) as client:  
                available = await list_available_tools(client)
                if tool_name not in available:
                    raise ValueError(f"Tool '{tool_name}' not found. Available: {available}")
                result = await client.call_tool(tool_name, tool_args or {})
                return extract_texts(result)
        else:
            async with streamablehttp_client(target, headers=headers) as (read, write, _sid):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    available = await list_available_tools(session)
                    if tool_name not in available:
                        raise ValueError(f"Tool '{tool_name}' not found. Available: {available}")
                    result = await session.call_tool(tool_name, tool_args or {})
                    return extract_texts(result)
    return asyncio.run(_runner())

def run_tool_with_timeout(tool_name: str, tool_args: Optional[Dict[str, Any]] = None, timeout: float = 115.0) -> List[str]:
    """Invoke a tool but cancel locally if it exceeds timeout seconds.

    Returns partial result texts if finished, raises TimeoutError if exceeded.
    Does NOT signal server-side cancellation; prefer async job endpoints for true server cancel.
    """
    async def _runner() -> List[str]:
        target = _normalize_url()
        token = _get_bearer_token(None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if _HAS_UNIFIED_CLIENT:
            async with Client(target, headers=headers) as client:  # type: ignore[arg-type]
                available = await list_available_tools(client)
                if tool_name not in available:
                    raise ValueError(f"Tool '{tool_name}' not found. Available: {available}")
                result = await asyncio.wait_for(client.call_tool(tool_name, tool_args or {}), timeout=timeout)
                return extract_texts(result)
        else:
            async with streamablehttp_client(target, headers=headers) as (read, write, _sid):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    available = await list_available_tools(session)
                    if tool_name not in available:
                        raise ValueError(f"Tool '{tool_name}' not found. Available: {available}")
                    result = await asyncio.wait_for(session.call_tool(tool_name, tool_args or {}), timeout=timeout)
                    return extract_texts(result)
    return asyncio.run(_runner())

# Async job REST helpers ----------------------------------------------------
def _job_base_url() -> str:
    raw = os.environ.get("MCP_SERVER_URL") or "http://127.0.0.1:8000"
    return raw.rstrip('/')

def submit_job_sync(tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Submit an async job via REST /api/jobs and return job metadata."""
    import urllib.request, json as _json
    body = _json.dumps({"tool": tool_name, "params": params or {}}).encode("utf-8")
    url = _job_base_url() + "/api/jobs"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return _json.loads(resp.read().decode("utf-8"))

def poll_job_sync(job_id: str) -> Dict[str, Any]:
    """Fetch job status and (if complete) result via GET /api/jobs/{job_id}."""
    import urllib.request, json as _json
    url = _job_base_url() + f"/api/jobs/{job_id}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return _json.loads(resp.read().decode("utf-8"))

def cancel_job_sync(job_id: str) -> Dict[str, Any]:
    """Cancel a running job via DELETE /api/jobs/{job_id}."""
    import urllib.request, json as _json
    url = _job_base_url() + f"/api/jobs/{job_id}"
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return _json.loads(resp.read().decode("utf-8"))

def _extract_prompt_text(prompt_obj: Any) -> str:
    """Return only the concatenated text portion of any prompt result.

    Always strips away role/content wrappers, returning raw text.
    Supports dict PromptObject, GetPromptResult(.messages), list of messages, or single message.
    """

    outputObj = ""
    if not prompt_obj:
        return ""

    # Fast path: dict with content.text
    if isinstance(prompt_obj, dict):
        content = prompt_obj.get("content")
        if isinstance(content, dict) and content.get("type") == "text":
            outputObj = (content.get("text") or "").strip()
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            outputObj = "\n".join(t for t in texts if t).strip()

    # Expand messages
    if hasattr(prompt_obj, "messages"):
        messages = getattr(prompt_obj, "messages") or []
    elif isinstance(prompt_obj, list):
        messages = prompt_obj
    else:
        messages = [prompt_obj]

    out: List[str] = []
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        if not content:
            continue
        # Single object
        if hasattr(content, "type") and getattr(content, "type", None) == "text":
            out.append(getattr(content, "text", ""))
            continue
        if isinstance(content, dict) and content.get("type") == "text":
            out.append(content.get("text", ""))
            continue
        if isinstance(content, list):
            for piece in content:
                if hasattr(piece, "type") and getattr(piece, "type", None) == "text":
                    out.append(getattr(piece, "text", ""))
                elif isinstance(piece, dict) and piece.get("type") == "text":
                    out.append(piece.get("text", ""))
    outputObj = "\n".join(t for t in out if t).strip()

    if isinstance(outputObj, str) and outputObj.startswith('{') and '"content"' in outputObj and '"text"' in outputObj:
                try:
                    import json as _json
                    obj = _json.loads(outputObj)
                    content = obj.get('content')
                    if isinstance(content, dict) and content.get('type') == 'text':
                        return (content.get('text') or '').strip()
                except Exception:
                    pass
    return outputObj


def get_prompt_sync(prompt_name: str) -> Any:
    """Fetch a prompt definition/content synchronously using MCP_SERVER_URL env."""

    async def _runner() -> Any:
        target = _normalize_url()
        token = _get_bearer_token(None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if _HAS_UNIFIED_CLIENT:
            async with Client(target, headers=headers) as client:  # type: ignore[arg-type]
                prompts = await list_available_prompts(client)
                if prompt_name not in prompts:
                    raise ValueError(f"Prompt '{prompt_name}' not found. Available: {prompts}")
                prompt = await client.get_prompt(prompt_name)
            text = _extract_prompt_text(prompt)
            # Final hard fallback: if still looks like role/content JSON, drill down.
            return text
        else:
            async with streamablehttp_client(target, headers=headers) as (read, write, _sid):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    prompts = await list_available_prompts(session)
                    if prompt_name not in prompts:
                        raise ValueError(f"Prompt '{prompt_name}' not found. Available: {prompts}")
                    prompt = await session.get_prompt(prompt_name)
                text = _extract_prompt_text(prompt)
                return text
    return asyncio.run(_runner())

def get_resource_sync(resource_uri: str) -> Any:
    """Fetch a resource's content synchronously.

    Args:
        resource_uri: Full resource URI (e.g. resource://offering-synonyms or template-expanded).
    Returns:
        Parsed content: str, bytes, or JSON-converted Python objects depending on server resource.
    Raises:
        ValueError if the resource is missing.
    """
    async def _runner() -> Any:
        target = _normalize_url()
        token = _get_bearer_token(None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if _HAS_UNIFIED_CLIENT:
            async with Client(target, headers=headers) as client:  # type: ignore[arg-type]
                resources = await list_available_resources(client)
                if str(resource_uri) not in resources:
                    raise ValueError(f"Resource '{resource_uri}' not found. Available: {resources}")
                result = await client.read_resource(resource_uri)
                contents = getattr(result, "contents", None)
                if not contents:
                    return None
                parsed_items: List[Any] = []
                for item in contents:
                    try:
                        mime = getattr(item, "mimeType", None)
                        text = getattr(item, "text", None)
                        data = getattr(item, "data", None)
                        if text is not None:
                            if mime == "application/json":
                                import json as _json
                                try:
                                    parsed_items.append(_json.loads(text))
                                except Exception:
                                    parsed_items.append(text)
                            else:
                                parsed_items.append(text)
                        elif data is not None:
                            parsed_items.append(data)
                        else:
                            parsed_items.append(item)
                    except Exception:
                        parsed_items.append(item)
                return parsed_items[0] if len(parsed_items) == 1 else parsed_items
        else:
            async with streamablehttp_client(target, headers=headers) as (read, write, _sid):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    resources = await list_available_resources(session)
                    if str(resource_uri) not in resources:
                        raise ValueError(f"Resource '{resource_uri}' not found. Available: {resources}")
                    result = await session.read_resource(resource_uri)
                    contents = getattr(result, "contents", None)
                    if not contents:
                        return None
                    parsed_items: List[Any] = []
                    for item in contents:
                        try:
                            mime = getattr(item, "mimeType", None)
                            text = getattr(item, "text", None)
                            data = getattr(item, "data", None)
                            if text is not None:
                                if mime == "application/json":
                                    import json as _json
                                    try:
                                        parsed_items.append(_json.loads(text))
                                    except Exception:
                                        parsed_items.append(text)
                                else:
                                    parsed_items.append(text)
                            elif data is not None:
                                parsed_items.append(data)
                            else:
                                parsed_items.append(item)
                        except Exception:
                            parsed_items.append(item)
                    return parsed_items[0] if len(parsed_items) == 1 else parsed_items
    return asyncio.run(_runner())


__all__ = [
    "run_tool",
    "run_tool_with_timeout",
    "get_prompt_sync",
    "list_available_tools",
    "list_available_prompts",
    "list_available_resources",
    "get_resource_sync",
    "submit_job_sync",
    "poll_job_sync",
    "cancel_job_sync",
]

# def build_parser() -> argparse.ArgumentParser:
#     parser = argparse.ArgumentParser(description="MCP client for invoking a tool or retrieving a prompt.")
#     parser.add_argument("tool", nargs="?", default=DEFAULT_TOOL, help="Tool name to invoke (default: %(default)s)")
#     parser.add_argument("python", nargs="?", default=os.environ.get("MCP_PYTHON", sys.executable), help="Python interpreter to launch server (ignored if --url is used)")
#     parser.add_argument("server", nargs="?", default=os.environ.get("MCP_SERVER_ENTRY", "__init__"), help="Server entry module path")
#     parser.add_argument("--retries", type=int, default=0, help="Retry attempts on failure")
#     parser.add_argument("--delay", type=float, default=0.75, help="Delay between retries")
#     parser.add_argument("--list", action="store_true", help="List available tools and exit")
#     parser.add_argument("--list-prompts", action="store_true", help="List available prompts and exit")
#     parser.add_argument("--prompt", metavar="NAME", help="Fetch prompt text instead of invoking a tool")
#     parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="Logging level")
#     parser.add_argument("--url", help="Remote MCP server base URL for streamable-http transport")
#     parser.add_argument("--transport", choices=["auto", "stdio", "streamable-http"], default="auto", help="Transport to use (default auto). If --url provided and auto, uses streamable-http")
#     parser.add_argument("--query", help="SQL query to pass when tool is run_tsql_query_tool")
#     parser.add_argument("--max-rows", type=int, dest="max_rows", help="Max rows to return (client side) for run_tsql_query_tool")
#     return parser

# def main(argv: Sequence[str] | None = None) -> int:
#     argv = list(argv) if argv is not None else sys.argv[1:]
#     parser = build_parser()
#     args = parser.parse_args(argv)
#     logging.getLogger().setLevel(args.log_level.upper())

#     transport = args.transport
#     url = args.url or os.environ.get("MCP_SERVER_URL")
#     if transport == "auto" and url:
#         transport = "streamable-http"
#     if transport == "streamable-http" and not url:
#         parser.error("--url is required when transport=streamable-http (or set MCP_SERVER_URL)")

#     # Force streamable-http only (stdio disabled)
#     if transport != "streamable-http":
#         if not url:
#             # Fallback: build default URL
#             url = "http://127.0.0.1:3001"
#         transport = "streamable-http"

#     if args.list:
#         return asyncio.run(list_mode_http(url))
#     if args.list_prompts:
#         return asyncio.run(list_prompts_mode_http(url))
#     if args.prompt:
#         return asyncio.run(fetch_prompt_http(args.prompt, url))

#     tool_args: Dict[str, Any] = {}
#     if args.tool == "run_tsql_query_tool":
#         if args.query:
#             tool_args["query"] = args.query
#         if args.max_rows is not None:
#             tool_args["max_rows"] = args.max_rows
#     return asyncio.run(invoke_tool_http(args.tool, url, tool_args))


# if __name__ == "__main__":  # pragma: no cover
#     raise SystemExit(main())

