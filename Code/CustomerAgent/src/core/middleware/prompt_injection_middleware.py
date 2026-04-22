"""
AgentMiddleware for prompt injection detection.

Runs BEFORE each agent execution.  Sends the latest user input to
an external prompt-injection detection API (e.g. Azure AI Content Safety
Prompt Shield).  If an injection attempt is detected, the middleware
short-circuits execution by raising ``MiddlewareTermination`` so the
agent never sees the malicious input.

Feature flag: set ENABLE_PROMPT_INJECTION=true to activate (default: false).
Per-agent toggle: ``"prompt_injection": true`` in agents_config.json.

Migration note: shared/middleware/prompt_injection_middleware.py has a generic
version. This file uses MAF-native AgentMiddleware with MiddlewareTermination
— keep as-is.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from agent_framework import AgentMiddleware, AgentContext, AgentResponse, MiddlewareTermination

from helper.agent_logger import AgentLogger, get_current_xcv
from helper.auth import get_auth_token

logger = logging.getLogger(__name__)

_INJECTION_ENABLED = os.getenv("ENABLE_PROMPT_INJECTION", "false").strip().lower() in ("true", "1", "yes")
INJECTION_ENABLED = _INJECTION_ENABLED  # public alias for agent_factory import
_INJECTION_API_URL = os.getenv("PROMPT_INJECTION_API_URL", "http://localhost:9001/shield")
_INJECTION_API_TIMEOUT = float(os.getenv("PROMPT_INJECTION_API_TIMEOUT", "5"))
_INJECTION_API_SCOPE = os.getenv("PROMPT_INJECTION_API_SCOPE", "").strip()


class PromptInjectionMiddleware(AgentMiddleware):
    """Checks agent input for prompt injection before execution.

    Usage:
        injection_mw = PromptInjectionMiddleware()
        agent = Agent(client=client, ..., middleware=[injection_mw])

    After each workflow run, call ``injection_mw.drain()`` to retrieve detections.
    """

    def __init__(self) -> None:
        self._detections: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear stored detections (call at start of each request)."""
        self._detections.clear()

    def drain(self) -> list[dict[str, Any]]:
        """Return and remove all accumulated detections since last drain."""
        result = list(self._detections)
        self._detections.clear()
        return result

    async def process(self, context: AgentContext, call_next) -> None:
        if not _INJECTION_ENABLED:
            await call_next()
            return

        agent_name = context.agent.name

        # Extract the latest user input to scan
        input_text = ""
        for msg in reversed(context.messages):
            if msg.role == "user" and msg.text:
                input_text = msg.text
                break

        if not input_text:
            await call_next()
            return

        # Call prompt injection detection API
        detection = await self._call_injection_api(agent_name, input_text)

        # Store every detection result (including safe ones) for audit trail
        self._detections.append(detection)

        # Log to agent logger
        xcv = get_current_xcv()
        is_injection = detection.get("is_injection", False)

        if xcv:
            AgentLogger.get_instance()._emit(
                "PromptInjection",
                xcv,
                {
                    "Agent": agent_name,
                    "IsInjection": is_injection,
                    "Confidence": detection.get("confidence", 0),
                    "Category": detection.get("category", ""),
                },
            )

        if is_injection:
            logger.warning(
                "[%s] Prompt injection DETECTED (confidence=%s, category=%s). Blocking execution.",
                agent_name,
                detection.get("confidence", "N/A"),
                detection.get("category", "unknown"),
            )
            # Terminate the middleware pipeline — agent never executes
            raise MiddlewareTermination(
                f"Prompt injection detected for agent '{agent_name}': "
                f"{detection.get('category', 'unknown')} "
                f"(confidence={detection.get('confidence', 'N/A')})"
            )

        logger.info(
            "[%s] Prompt injection check: safe (confidence=%s)",
            agent_name, detection.get("confidence", "N/A"),
        )

        # Input is safe — proceed with agent execution
        await call_next()

    async def _call_injection_api(
        self,
        agent_name: str,
        input_text: str,
    ) -> dict[str, Any]:
        """POST input text to the prompt injection detection endpoint.

        Expected response JSON shape:
            {
                "is_injection": bool,
                "confidence": float,   # 0.0–1.0
                "category": str        # e.g. "jailbreak", "indirect_injection"
            }
        """
        payload = {
            "agent_name": agent_name,
            "input": input_text,
        }

        xcv = get_current_xcv()
        headers = {}
        if xcv:
            headers["X-XCV"] = xcv

        # Attach Bearer token when a scope is configured
        token = get_auth_token(_INJECTION_API_SCOPE)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    _INJECTION_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=_INJECTION_API_TIMEOUT,
                )
                resp.raise_for_status()
                result = resp.json()
                result["agent_name"] = agent_name
                elapsed = round((time.monotonic() - t0) * 1000, 1)
                result["duration_ms"] = elapsed

                # Log API call details
                if xcv:
                    AgentLogger.get_instance().log_injection_api_call(
                        xcv=xcv,
                        agent_name=agent_name,
                        api_url=_INJECTION_API_URL,
                        input_text=input_text,
                        http_status=resp.status_code,
                        response_body=resp.text,
                        is_injection=result.get("is_injection", False),
                        confidence=result.get("confidence", 0),
                        category=result.get("category", ""),
                        duration_ms=elapsed,
                    )

                return result
        except Exception as exc:
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.warning("[%s] Prompt injection API failed: %s — allowing execution", agent_name, exc)

            # Log failed API call
            if xcv:
                AgentLogger.get_instance().log_injection_api_call(
                    xcv=xcv,
                    agent_name=agent_name,
                    api_url=_INJECTION_API_URL,
                    input_text=input_text,
                    duration_ms=elapsed,
                    error=str(exc),
                )

            # Fail-open: if the injection API is unreachable, allow execution
            return {
                "agent_name": agent_name,
                "is_injection": False,
                "confidence": 0,
                "category": "",
                "error": str(exc),
                "duration_ms": elapsed,
            }
