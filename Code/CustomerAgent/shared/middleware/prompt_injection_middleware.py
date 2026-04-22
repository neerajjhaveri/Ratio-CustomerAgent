"""Prompt Injection middleware — screens prompts through the AI Safety Eval Service container.

This is a ChatMiddleware that runs on EVERY model call (including tool-result
callbacks). It sends the user message to the prompt injection detection
container and blocks the request if an injection is detected.

The AI Safety Eval Service stays in its own container — this middleware is
just a thin async HTTP client that calls it synchronously in the chat pipeline.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

from agent_framework import (
    ChatContext,
    ChatMiddleware,
    ChatResponse,
    Message,
    MiddlewareTermination,
)

logger = logging.getLogger(__name__)


class PromptInjectionMiddleware(ChatMiddleware):
    """Chat middleware that screens every model call through the PI container.

    Intercepts at the chat level (before the model sees the prompt) and sends
    the latest user message to the prompt injection detection service. If an
    injection is detected, the middleware terminates execution with a safe response.

    The PI container exposes: POST /api/v1/evaluations/prompt-injection
    Request:  {"prompt": "..."}
    Response: {"is_injection": true/false, "confidence": 0.95, "category": "..."}

    Args:
        pi_service_url: Base URL of the AI Safety Eval Service container.
        timeout_seconds: HTTP timeout for the PI check. Must be fast.
        confidence_threshold: Minimum confidence to trigger a block.
    """

    def __init__(
        self,
        pi_service_url: str = "http://127.0.0.1:8000",
        timeout_seconds: float = 3.0,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._pi_url = f"{pi_service_url}/api/v1/evaluations/prompt-injection"
        self._timeout = timeout_seconds
        self._confidence_threshold = confidence_threshold

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        if not _AIOHTTP_AVAILABLE:
            logger.debug("[PromptInjection] aiohttp not installed — skipping")
            await call_next()
            return

        # Find the latest user message
        user_text = ""
        for msg in reversed(context.messages):
            if msg.role == "user" and hasattr(msg, "text") and msg.text:
                user_text = msg.text
                break

        if not user_text:
            await call_next()
            return

        # Screen through PI container
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._pi_url,
                    json={"prompt": user_text},
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        is_injection = result.get("is_injection", False)
                        confidence = result.get("confidence", 0.0)

                        if is_injection and confidence >= self._confidence_threshold:
                            category = result.get("category", "unknown")
                            logger.warning(
                                "[PromptInjection] BLOCKED — injection detected "
                                "(confidence=%.2f, category=%s): %s",
                                confidence, category, user_text[:100],
                            )
                            context.result = ChatResponse(
                                messages=[Message(role="assistant", contents=[
                                    "Your request was blocked by our safety system. "
                                    "The message appears to contain a prompt injection attempt. "
                                    "Please rephrase your question."
                                ])]
                            )
                            raise MiddlewareTermination
                        else:
                            logger.debug(
                                "[PromptInjection] Clean (is_injection=%s, confidence=%.2f)",
                                is_injection, confidence,
                            )
                    else:
                        logger.warning("[PromptInjection] PI service returned status %d — allowing through", resp.status)
        except MiddlewareTermination:
            raise  # Re-raise termination
        except aiohttp.ClientConnectorError:
            logger.debug("[PromptInjection] PI service not reachable — allowing through")
        except Exception as exc:
            logger.warning("[PromptInjection] PI check failed (allowing through): %s", exc)

        # Clean — proceed to model
        await call_next()
