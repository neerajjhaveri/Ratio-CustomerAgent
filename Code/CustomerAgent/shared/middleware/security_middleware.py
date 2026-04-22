"""Security middleware — blocks sensitive content before it reaches the LLM."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    AgentResponse,
    Message,
    MiddlewareTermination,
)

logger = logging.getLogger(__name__)

_BLOCKED_TERMS = [
    "password", "secret", "api_key", "api key", "access_token",
    "access token", "private_key", "private key", "connection_string",
    "connection string", "credentials",
]

_PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),       # SSN
    re.compile(r"\b\d{16}\b"),                     # Credit card (simple)
    re.compile(r"\b[A-Za-z0-9+/]{40,}\b"),         # Base64 keys (40+ chars)
]


class SecurityMiddleware(AgentMiddleware):
    """Blocks requests containing sensitive information (passwords, PII, etc.).

    Uses ``MiddlewareTermination`` to stop the chain and return a safe response.
    """

    def __init__(
        self,
        blocked_terms: list[str] | None = None,
        block_pii: bool = True,
    ) -> None:
        self._blocked_terms = [t.lower() for t in (_BLOCKED_TERMS + (blocked_terms or []))]
        self._block_pii = block_pii

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        last_message = context.messages[-1] if context.messages else None
        if last_message and last_message.text:
            text = last_message.text
            text_lower = text.lower()

            # Check blocked terms
            for term in self._blocked_terms:
                if term in text_lower:
                    logger.warning("[Security] Blocked term '%s' detected — terminated", term)
                    context.result = AgentResponse(
                        messages=[Message(role="assistant", contents=[
                            "I cannot process requests containing sensitive information "
                            "such as passwords, API keys, or tokens. "
                            "Please rephrase your question without including sensitive data."
                        ])]
                    )
                    raise MiddlewareTermination(result=context.result)

            # Check PII patterns
            if self._block_pii:
                for pattern in _PII_PATTERNS:
                    if pattern.search(text):
                        logger.warning("[Security] PII pattern detected — terminated")
                        context.result = AgentResponse(
                            messages=[Message(role="assistant", contents=[
                                "I detected what appears to be personally identifiable "
                                "information (PII) in your message. Please remove any "
                                "SSNs, credit card numbers, or other sensitive data."
                            ])]
                        )
                        raise MiddlewareTermination(result=context.result)

        context.metadata["security_validated"] = True
        await call_next()
