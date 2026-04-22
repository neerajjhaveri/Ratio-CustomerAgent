"""
ChatMiddleware for logging every LLM (chat completion) call.

Intercepts each request from an agent to the LLM to record:
  - Agent name (from metadata)
  - Model name
  - Message count sent
  - Response text & finish reason
  - Token usage (input / output / total)
  - Latency

The captured data is stored in a shared list on the middleware instance that the
orchestrator can drain for UI display or telemetry.

Feature flag: set ENABLE_LLM_LOGGING=true to activate (default: true).
Per-agent toggle: ``"llm_logging": true`` in agents_config.json.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from agent_framework import ChatMiddleware, ChatContext, ChatResponse, ResponseStream

from helper.agent_logger import AgentLogger, get_current_xcv

logger = logging.getLogger(__name__)

_LLM_LOGGING_ENABLED = os.getenv("ENABLE_LLM_LOGGING", "true").strip().lower() in ("true", "1", "yes")
LLM_LOGGING_ENABLED = _LLM_LOGGING_ENABLED  # public alias for agent_factory import


class LLMLoggingMiddleware(ChatMiddleware):
    """Logs every LLM chat completion call with timing and token usage.

    Usage:
        llm_mw = LLMLoggingMiddleware(agent_name="my_agent")
        agent = Agent(client=client, ..., middleware=[llm_mw])

    After each workflow run, call ``llm_mw.drain()`` to retrieve logged calls.
    All per-agent instances share a class-level call list so a single drain()
    returns data from every agent.
    """

    _shared_calls: list[dict[str, Any]] = []

    def __init__(self, agent_name: str = "") -> None:
        self._agent_name = agent_name

    def reset(self) -> None:
        """Clear stored LLM call logs (call at start of each request)."""
        self.__class__._shared_calls.clear()

    def drain(self) -> list[dict[str, Any]]:
        """Return and remove all accumulated LLM call logs since last drain."""
        result = list(self.__class__._shared_calls)
        self.__class__._shared_calls.clear()
        return result

    async def process(self, context: ChatContext, call_next) -> None:
        if not _LLM_LOGGING_ENABLED:
            await call_next()
            return

        agent_name = self._agent_name or context.metadata.get("agent_name", "") if context.metadata else self._agent_name
        model = context.options.get("model", "unknown") if context.options else "unknown"
        message_count = len(context.messages) if context.messages else 0

        entry: dict[str, Any] = {
            "agent": agent_name,
            "model": model,
            "message_count": message_count,
            "response_text": "",
            "finish_reason": "",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "duration_ms": 0,
            "error": None,
        }

        deferred = False  # True when a stream hook will finalize later
        start = time.monotonic()
        try:
            await call_next()

            result = context.result
            if isinstance(result, ChatResponse):
                self._extract_response(result, entry, model)
            elif isinstance(result, ResponseStream):
                # For streaming: hook into the finalized response after the
                # stream has been fully consumed so we capture tokens/text.
                deferred = True

                def _make_hook(e=entry, m=model, s=start, a=agent_name, mc=message_count):
                    def _on_final(response: ChatResponse) -> ChatResponse:
                        self._extract_response(response, e, m)
                        self._finalize_entry(e, s, a, mc)
                        return response
                    return _on_final
                context.stream_result_hooks.append(_make_hook())

        except Exception as exc:
            entry["error"] = str(exc)
            raise
        finally:
            if not deferred:
                self._finalize_entry(entry, start, agent_name, message_count)

    def _extract_response(
        self, result: ChatResponse, entry: dict[str, Any], fallback_model: str,
    ) -> None:
        """Extract response details from a ChatResponse into the entry dict."""
        entry["model"] = result.model or fallback_model
        entry["finish_reason"] = str(result.finish_reason or "")

        # Response text — use .text property if available, else iterate messages
        text = getattr(result, "text", None) or ""
        if not text and result.messages:
            texts = [m.text for m in result.messages if m.text]
            text = "\n".join(texts)
        _llm_max = int(os.getenv("LOG_MAX_CHARS", "0"))
        if _llm_max > 0 and len(text) > _llm_max:
            entry["response_text"] = text[:_llm_max] + f"... ({len(text)} chars)"
        else:
            entry["response_text"] = text

        # Token usage
        if result.usage_details:
            entry["input_tokens"] = result.usage_details.get("input_token_count")
            entry["output_tokens"] = result.usage_details.get("output_token_count")
            entry["total_tokens"] = result.usage_details.get("total_token_count")

    def _finalize_entry(
        self,
        entry: dict[str, Any],
        start: float,
        agent_name: str,
        message_count: int,
    ) -> None:
        """Record timing, store entry, and emit to AgentLogger."""
        elapsed = (time.monotonic() - start) * 1000
        entry["duration_ms"] = round(elapsed, 1)

        self.__class__._shared_calls.append(entry)

        # Log to AgentLogger / App Insights
        xcv = get_current_xcv()
        if xcv:
            AgentLogger.get_instance().log_llm_call(
                xcv=xcv,
                agent_name=agent_name or "unknown",
                model=entry["model"],
                message_count=message_count,
                response_text=entry.get("response_text", ""),
                finish_reason=entry.get("finish_reason", ""),
                input_tokens=entry.get("input_tokens"),
                output_tokens=entry.get("output_tokens"),
                total_tokens=entry.get("total_tokens"),
                duration_ms=elapsed,
                error=entry.get("error", ""),
            )

        logger.info(
            "[%s] LLM call → model=%s, messages=%d, tokens=%s, %.0fms %s",
            agent_name or "agent",
            entry["model"],
            message_count,
            entry.get("total_tokens", "?"),
            elapsed,
            "✓" if not entry["error"] else f"✗ {entry['error'][:80]}",
        )
