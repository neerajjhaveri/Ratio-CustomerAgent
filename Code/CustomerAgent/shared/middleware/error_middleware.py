"""Error handling middleware — graceful tool failure recovery."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from agent_framework import FunctionInvocationContext, FunctionMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(FunctionMiddleware):
    """Catches exceptions from tool execution and returns user-friendly errors.

    Prevents raw Python exceptions from reaching the LLM, which would
    confuse the model and produce poor responses.
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        func_name = context.function.name

        try:
            await call_next()
        except TimeoutError as exc:
            logger.error("[ErrorHandler] %s timed out: %s", func_name, exc)
            context.result = (
                f"The tool '{func_name}' timed out. "
                "The service may be temporarily unavailable. "
                "Please try again or use a different approach."
            )
        except ConnectionError as exc:
            logger.error("[ErrorHandler] %s connection error: %s", func_name, exc)
            context.result = (
                f"The tool '{func_name}' could not connect to its data source. "
                "The service may be down. Please try again later."
            )
        except PermissionError as exc:
            logger.error("[ErrorHandler] %s permission denied: %s", func_name, exc)
            context.result = (
                f"The tool '{func_name}' does not have permission to access "
                "the requested resource. Contact your administrator."
            )
        except Exception as exc:
            logger.error("[ErrorHandler] %s unexpected error: %s", func_name, exc, exc_info=True)
            context.result = (
                f"The tool '{func_name}' encountered an unexpected error: {type(exc).__name__}. "
                "The error has been logged. Please try a different approach."
            )
