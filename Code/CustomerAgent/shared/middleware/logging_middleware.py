"""Logging middleware — structured timing, request/response logging, and App Insights telemetry."""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
)

logger = logging.getLogger(__name__)

# Optional App Insights integration
_APPINSIGHTS_AVAILABLE = False
try:
    from opencensus.ext.azure.trace_exporter import AzureExporter
    _APPINSIGHTS_AVAILABLE = True
except ImportError:
    pass


class LoggingAgentMiddleware(AgentMiddleware):
    """Logs every agent invocation with timing, agent name, and message count.

    Sets ``metadata["request_id"]`` and ``metadata["duration_ms"]`` for
    downstream middleware to consume.
    """

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        request_id = str(uuid.uuid4())[:8]
        context.metadata["request_id"] = request_id

        agent_name = getattr(context.agent, "name", "unknown")
        msg_count = len(context.messages)
        is_stream = context.stream

        logger.info(
            "[%s] Agent=%s messages=%d stream=%s — started",
            request_id,
            agent_name,
            msg_count,
            is_stream,
        )

        start = time.perf_counter()
        try:
            await call_next()
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            context.metadata["duration_ms"] = duration_ms

            result_chars = 0
            if context.result and hasattr(context.result, "text") and context.result.text:
                result_chars = len(context.result.text)

            logger.info(
                "[%s] Agent=%s — completed in %.1fms (response_chars=%d)",
                request_id,
                agent_name,
                duration_ms,
                result_chars,
            )


class ToolTimingMiddleware(FunctionMiddleware):
    """Logs every tool/function call with argument summary and duration."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        func_name = context.function.name
        args_summary = {}
        if context.arguments:
            for k, v in context.arguments.items():
                s = str(v)
                args_summary[k] = s[:80] + "..." if len(s) > 80 else s

        logger.info("[Tool] %s called with %s", func_name, args_summary)

        start = time.perf_counter()
        await call_next()
        duration_ms = (time.perf_counter() - start) * 1000

        result_preview = ""
        if context.result:
            r = str(context.result)
            result_preview = r[:120] + "..." if len(r) > 120 else r

        logger.info(
            "[Tool] %s completed in %.1fms — result: %s",
            func_name,
            duration_ms,
            result_preview,
        )
