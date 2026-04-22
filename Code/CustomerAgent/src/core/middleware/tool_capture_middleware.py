"""
MAF FunctionMiddleware for capturing tool calls, queries, and results.

Intercepts every MCP tool invocation to record:
  - Agent name (from metadata)
  - Tool name & arguments (including SQL query)
  - Execution result (dataset / error)
  - Timing

The captured data is stored in a shared list on the middleware instance that the
orchestrator reads after each agent turn for UI display in expanders.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

from agent_framework import FunctionInvocationContext, FunctionMiddleware

from helper.agent_logger import AgentLogger, get_current_xcv

logger = logging.getLogger(__name__)


def _serialize_result(result: Any) -> str:
    """Convert a tool-call result (often a list of Content objects) to a readable string."""
    # agent_framework tool results are typically list[Content]
    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            if hasattr(item, "to_dict"):
                d = item.to_dict()
                # For text content, just grab the text value
                if d.get("type") == "text" and "text" in d:
                    parts.append(d["text"])
                else:
                    parts.append(json.dumps(d, default=str))
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else "(empty list)"
    if hasattr(result, "to_dict"):
        d = result.to_dict()
        if d.get("type") == "text" and "text" in d:
            return d["text"]
        return json.dumps(d, default=str)
    return str(result)


class ToolCallCaptureMiddleware(FunctionMiddleware):
    """Captures tool invocations (queries, results, timing) for UI display.

    Usage:
        middleware = ToolCallCaptureMiddleware()
        agent = Agent(client=client, ..., middleware=[middleware])

    Before each request, call `middleware.reset()` to start fresh.
    After each agent turn, call `middleware.drain()` to retrieve new captures.
    """

    def __init__(self) -> None:
        self._captures: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear all captured tool calls (call at start of each request)."""
        self._captures.clear()
        logger.info("ToolCallCaptureMiddleware: reset captures")

    def drain(self) -> list[dict[str, Any]]:
        """Return and remove all accumulated captures since last drain."""
        result = list(self._captures)
        self._captures.clear()
        return result

    @property
    def captures(self) -> list[dict[str, Any]]:
        """Read-only view of current captures (does not clear)."""
        return list(self._captures)

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next,
    ) -> None:
        tool_name = context.function.name if context.function else "unknown"
        logger.info(">>> MIDDLEWARE INVOKED for tool: %s", tool_name)

        # ── Extract arguments ────────────────────────────────
        args_dict: dict[str, Any] = {}
        if context.arguments:
            if hasattr(context.arguments, "model_dump"):
                args_dict = context.arguments.model_dump()
            elif isinstance(context.arguments, dict):
                args_dict = dict(context.arguments)
            else:
                try:
                    args_dict = dict(context.arguments)
                except Exception:
                    args_dict = {"raw": str(context.arguments)}

        # Extract SQL query if present
        query_text = args_dict.get("query", "")
        logger.info(">>> MIDDLEWARE args keys: %s, query present: %s", list(args_dict.keys()), bool(query_text))

        # ── Sanitize Unicode operators in SQL queries ────────
        # LLMs sometimes emit ≥ ≤ ≠ instead of >= <= <>
        if query_text and any(ch in query_text for ch in ("≥", "≤", "≠")):
            sanitized = query_text.replace("≥", ">=").replace("≤", "<=").replace("≠", "<>")
            logger.warning("Sanitized Unicode operators in SQL query for tool %s", tool_name)
            args_dict["query"] = sanitized
            query_text = sanitized
            # Push sanitized args back to context so the tool gets clean SQL
            if isinstance(context.arguments, dict):
                context.arguments["query"] = sanitized
            elif hasattr(context.arguments, "__setitem__"):
                context.arguments["query"] = sanitized
            elif hasattr(context.arguments, "model_copy"):
                context.arguments = context.arguments.model_copy(update={"query": sanitized})
            else:
                # Last resort: replace the entire arguments object
                new_args = dict(args_dict)
                context.arguments = new_args

        # ── Agent name from metadata ─────────────────────────
        agent_name = ""
        if context.metadata:
            agent_name = context.metadata.get("agent_name", "")
        # When sub-agents are used as tools (via as_tool()), metadata may not
        # carry the agent name.  Fall back to the function's plugin_name which
        # the framework sets to the originating agent name.
        if not agent_name:
            fn = context.function
            if fn is not None:
                agent_name = getattr(fn, "plugin_name", "") or ""
        if not agent_name:
            agent_name = tool_name  # last resort: use the tool name itself

        capture: dict[str, Any] = {
            "agent": agent_name,
            "tool": tool_name,
            "arguments": args_dict,
            "query": query_text,
            "result": None,
            "error": None,
            "duration_ms": 0,
        }

        # ── Execute the actual tool ──────────────────────────
        start = time.monotonic()
        try:
            await call_next()

            # Capture the result
            result = context.result
            if result is not None:
                result_str = _serialize_result(result)
                _tool_max = int(os.getenv("LOG_MAX_CHARS", "0"))
                if _tool_max > 0 and len(result_str) > _tool_max:
                    capture["result"] = result_str[:_tool_max] + f"\n... ({len(result_str)} chars total)"
                else:
                    capture["result"] = result_str
            else:
                capture["result"] = "(no result)"

        except Exception as exc:
            capture["error"] = str(exc)
            raise  # Re-raise so the agent sees the error
        finally:
            elapsed = (time.monotonic() - start) * 1000
            capture["duration_ms"] = round(elapsed, 1)

            # Store on the instance
            self._captures.append(capture)

            # ── Log to agent logger ──────────────────────────
            xcv = get_current_xcv()
            if xcv:
                AgentLogger.get_instance().log_tool_call(
                    xcv=xcv,
                    agent_name=agent_name or "unknown",
                    tool_name=tool_name,
                    arguments=args_dict,
                    result=capture.get("result"),
                    error=capture.get("error"),
                    duration_ms=elapsed,
                )

            logger.info(
                ">>> MIDDLEWARE captured: %s → %s (%.0fms) %s  [total captures: %d]",
                agent_name or "agent",
                tool_name,
                elapsed,
                "✓" if not capture["error"] else f"✗ {capture['error'][:80]}",
                len(self._captures),
            )
