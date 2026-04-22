"""
AgentMiddleware that evaluates agent output by calling an external evaluation API.

Runs after each agent produces a response. Sends the agent's output to a
configurable evaluation endpoint and stores the score/feedback for downstream
consumption (orchestrator SSE events, logging).

Feature flag: set ENABLE_AGENT_EVALUATION=true to activate (default: false).

Migration note: shared/middleware/eval_middleware.py has a generic version.
This file uses MAF-native AgentMiddleware with drain()/reset() — keep as-is.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from agent_framework import AgentMiddleware, AgentContext, AgentResponse

from helper.agent_logger import AgentLogger, get_current_xcv
from helper.auth import get_auth_token

logger = logging.getLogger(__name__)

_EVAL_ENABLED = os.getenv("ENABLE_AGENT_EVALUATION", "false").strip().lower() in ("true", "1", "yes")
EVAL_ENABLED = _EVAL_ENABLED  # public alias for agent_factory import
_EVAL_API_URL = os.getenv("EVAL_API_URL", "http://localhost:9000/evaluate")
_EVAL_API_TIMEOUT = float(os.getenv("EVAL_API_TIMEOUT", "10"))
_EVAL_API_SCOPE = os.getenv("EVAL_API_SCOPE", "").strip()


class OutputEvaluationMiddleware(AgentMiddleware):
    """Sends each agent's output to an evaluation API after execution.

    Usage:
        eval_mw = OutputEvaluationMiddleware()
        agent = Agent(client=client, ..., middleware=[eval_mw])

    After each workflow run, call ``eval_mw.drain()`` to retrieve evaluations.
    """

    def __init__(self) -> None:
        self._evaluations: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear stored evaluations (call at start of each request)."""
        self._evaluations.clear()

    def drain(self) -> list[dict[str, Any]]:
        """Return and remove all accumulated evaluations since last drain."""
        result = list(self._evaluations)
        self._evaluations.clear()
        return result

    async def process(self, context: AgentContext, call_next) -> None:
        # Let the agent run normally
        await call_next()

        if not _EVAL_ENABLED:
            return

        result = context.result
        if result is None:
            return

        agent_name = context.agent.name

        # Handle non-streaming AgentResponse
        if isinstance(result, AgentResponse):
            output_text = "\n".join(m.text for m in result.messages if m.text)
            if not output_text:
                return

            # Build input context from the last user message
            input_text = ""
            for msg in reversed(context.messages):
                if msg.role == "user" and msg.text:
                    input_text = msg.text
                    break

            evaluation = await self._call_eval_api(
                agent_name=agent_name,
                input_text=input_text,
                output_text=output_text,
            )

            # Store for drain
            self._evaluations.append(evaluation)

            # Also attach to context metadata so downstream middleware can see it
            context.metadata["evaluation"] = evaluation

            # Log to agent logger
            xcv = get_current_xcv()
            if xcv:
                AgentLogger.get_instance().log_agent_response(
                    xcv, agent_name,
                    f"[EVAL score={evaluation.get('score', 'N/A')}] {output_text[:200]}",
                )

            logger.info(
                "[%s] Evaluation complete: score=%s",
                agent_name, evaluation.get("score", "N/A"),
            )

    async def _call_eval_api(
        self,
        agent_name: str,
        input_text: str,
        output_text: str,
    ) -> dict[str, Any]:
        """POST agent output to the evaluation endpoint."""
        payload = {
            "agent_name": agent_name,
            "input": input_text,
            "output": output_text,
        }

        xcv = get_current_xcv()
        headers = {}
        if xcv:
            headers["X-XCV"] = xcv

        # Attach Bearer token when a scope is configured
        token = get_auth_token(_EVAL_API_SCOPE)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    _EVAL_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=_EVAL_API_TIMEOUT,
                )
                resp.raise_for_status()
                result = resp.json()
                result["agent_name"] = agent_name
                elapsed = round((time.monotonic() - t0) * 1000, 1)
                result["duration_ms"] = elapsed

                # Log API call details
                if xcv:
                    AgentLogger.get_instance().log_eval_api_call(
                        xcv=xcv,
                        agent_name=agent_name,
                        api_url=_EVAL_API_URL,
                        input_text=input_text,
                        output_text=output_text,
                        http_status=resp.status_code,
                        response_body=resp.text,
                        score=result.get("score"),
                        feedback=result.get("feedback", ""),
                        duration_ms=elapsed,
                    )

                return result
        except Exception as exc:
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.warning("[%s] Evaluation API failed: %s", agent_name, exc)

            # Log failed API call
            if xcv:
                AgentLogger.get_instance().log_eval_api_call(
                    xcv=xcv,
                    agent_name=agent_name,
                    api_url=_EVAL_API_URL,
                    input_text=input_text,
                    output_text=output_text,
                    duration_ms=elapsed,
                    error=str(exc),
                )

            return {
                "agent_name": agent_name,
                "score": None,
                "error": str(exc),
                "duration_ms": elapsed,
            }
