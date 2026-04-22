"""Eval middleware — ratio_eval_sidecar integration for automated response quality scoring.

Runs AFTER the agent completes (post-execution). Non-blocking — eval failure
never breaks the agent response.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

from agent_framework import AgentContext, AgentMiddleware

logger = logging.getLogger(__name__)


class EvalMiddleware(AgentMiddleware):
    """Post-execution quality evaluation via the ratio_eval_sidecar service.

    Sends (query, answer) to the eval sidecar for scoring. Stores scores
    in ``context.metadata["eval_scores"]`` for downstream consumers.

    Args:
        enabled: Whether evaluation is active. Disabled by default.
        eval_sidecar_url: Base URL of the eval sidecar (default: localhost:8011).
        min_quality_score: Log a warning if overall score drops below this threshold.
    """

    def __init__(
        self,
        enabled: bool = False,
        eval_sidecar_url: str = "http://127.0.0.1:8011",
        min_quality_score: float = 0.0,
    ) -> None:
        self._enabled = enabled
        self._eval_url = eval_sidecar_url
        self._min_score = min_quality_score

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        # Always let the agent complete first
        await call_next()

        if not self._enabled:
            return

        if not _AIOHTTP_AVAILABLE:
            logger.warning("[Eval] aiohttp not installed — skipping evaluation")
            return

        # Extract query and response
        query = ""
        for msg in reversed(context.messages):
            if msg.role == "user" and hasattr(msg, "text") and msg.text:
                query = msg.text
                break

        response_text = ""
        if context.result and hasattr(context.result, "text") and context.result.text:
            response_text = context.result.text

        if not query or not response_text:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._eval_url}/v1/evaluations",
                    json={
                        "query": query,
                        "answer": response_text,
                        "include_ai_quality": True,
                        "include_completeness": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=10.0),
                ) as resp:
                    if resp.status == 200:
                        scores = await resp.json()
                        context.metadata["eval_scores"] = scores
                        overall = scores.get("overall", scores.get("score", 1.0))
                        agent_name = getattr(context.agent, "name", "unknown")
                        if isinstance(overall, (int, float)) and overall < self._min_score:
                            logger.warning(
                                "[Eval] Agent=%s response scored %.2f (below threshold %.2f)",
                                agent_name, overall, self._min_score,
                            )
                        else:
                            logger.info("[Eval] Agent=%s scored: %s", agent_name, scores)
                    else:
                        logger.warning("[Eval] Sidecar returned status %d", resp.status)
        except Exception as exc:
            logger.debug("[Eval] Evaluation failed (non-blocking): %s", exc)


class ContentFilterMiddleware(AgentMiddleware):
    """Placeholder for Azure Content Safety integration.

    When enabled, will check agent responses against Azure Content Safety
    and override unsafe responses. Currently a no-op.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        await call_next()

        if not self._enabled:
            return

        # TODO: Integrate with Azure Content Safety API
        # POST context.result.text to Content Safety endpoint
        # If unsafe, override context.result with safe message
        logger.debug("[ContentFilter] Enabled but not yet implemented")
