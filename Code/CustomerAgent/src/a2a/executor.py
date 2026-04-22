"""A2A Executor for MAF Agents.

Wraps a MAF ``Agent`` instance to handle A2A JSON-RPC requests.
Runs the agent, captures tool calls via middleware, and returns
structured output compatible with the A2A protocol.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator

from agent_framework import Agent

from .agent_card import AgentCard
from .schemas import A2AJsonRpcRequest, A2AStreamChunk

logger = logging.getLogger("a2a.executor")


class A2AExecutor:
    """Executes an A2A request against a MAF Agent.

    Parameters
    ----------
    card : AgentCard
        Discovery metadata for this agent.
    agent : Agent
        The MAF Agent instance (already created by agent_factory).
    capture_middleware : ToolCallCaptureMiddleware | None
        Shared middleware for capturing tool calls.
    """

    def __init__(
        self,
        card: AgentCard,
        agent: Agent,
        capture_middleware: Any = None,
    ):
        self._card = card
        self._agent = agent
        self._capture_mw = capture_middleware

    @property
    def agent_card(self) -> AgentCard:
        return self._card

    async def execute(self, req: A2AJsonRpcRequest, user_token: str | None = None) -> dict[str, Any]:
        """Run the agent and return the full A2A response result dict."""
        # Extract user text from A2A message parts
        user_text = "\n".join(
            p.text for p in req.params.message.parts if p.type == "text"
        )

        if not user_text.strip():
            return {
                "output": {"text": "Empty query.", "error": "No input provided."},
                "agent": self._card.to_dict(),
            }

        # Set user token for SQL passthrough
        if user_token:
            from helper.auth import set_user_token
            set_user_token(user_token)

        # Reset middleware captures
        if self._capture_mw:
            self._capture_mw.reset()

        start_time = time.time()

        try:
            # Run the agent (non-streaming for A2A)
            response = await self._agent.run(user_text)
            elapsed_ms = (time.time() - start_time) * 1000

            # Extract text output
            output_text = response.text or ""

            # Drain tool calls from middleware
            tool_calls = []
            if self._capture_mw:
                captures = self._capture_mw.drain()
                for cap in captures:
                    tool_calls.append({
                        "tool": cap.get("tool", ""),
                        "query": cap.get("query", ""),
                        "arguments": cap.get("arguments", {}),
                        "duration_ms": cap.get("duration_ms", 0),
                        "error": cap.get("error"),
                    })

            logger.info(
                "[%s] A2A execute completed in %.0fms (tool_calls=%d, output_len=%d)",
                self._card.name, elapsed_ms, len(tool_calls), len(output_text),
            )

            return {
                "output": {
                    "text": output_text,
                    "tool_calls": tool_calls,
                },
                "elapsed_ms": elapsed_ms,
                "agent": self._card.to_dict(),
            }

        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.exception("[%s] A2A execute failed: %s", self._card.name, exc)
            return {
                "output": {"text": "", "error": str(exc)},
                "elapsed_ms": elapsed_ms,
                "agent": self._card.to_dict(),
            }

    async def stream(self, req: A2AJsonRpcRequest, user_token: str | None = None) -> AsyncGenerator[A2AStreamChunk, None]:
        """Stream the agent execution as A2A stream chunks.

        Yields chunks: status → working, then end → final output.
        """
        user_text = "\n".join(
            p.text for p in req.params.message.parts if p.type == "text"
        )

        if not user_text.strip():
            yield A2AStreamChunk(
                id=req.id,
                params={"event": "end", "output": {"text": "Empty query."}},
            )
            return

        # Set user token
        if user_token:
            from helper.auth import set_user_token
            set_user_token(user_token)

        # Reset middleware
        if self._capture_mw:
            self._capture_mw.reset()

        # Status: working
        yield A2AStreamChunk(
            id=req.id,
            params={
                "event": "status",
                "status": "working",
                "agent": self._card.name,
            },
        )

        start_time = time.time()

        try:
            # Stream the agent response
            response_stream = self._agent.run(user_text, stream=True)
            full_text = ""

            async for update in response_stream:
                chunk_text = update.text if hasattr(update, "text") and update.text else ""
                if chunk_text:
                    full_text += chunk_text
                    yield A2AStreamChunk(
                        id=req.id,
                        params={
                            "event": "chunk",
                            "text": chunk_text,
                            "agent": self._card.name,
                        },
                    )

            # If streaming returned an AgentResponse at the end, get its text
            if hasattr(response_stream, "value"):
                final_response = response_stream.value
                if hasattr(final_response, "text") and final_response.text:
                    full_text = final_response.text

            elapsed_ms = (time.time() - start_time) * 1000

            # Drain tool calls
            tool_calls = []
            if self._capture_mw:
                captures = self._capture_mw.drain()
                for cap in captures:
                    tool_calls.append({
                        "tool": cap.get("tool", ""),
                        "query": cap.get("query", ""),
                        "arguments": cap.get("arguments", {}),
                        "duration_ms": cap.get("duration_ms", 0),
                        "error": cap.get("error"),
                    })

            # End chunk with full output
            yield A2AStreamChunk(
                id=req.id,
                params={
                    "event": "end",
                    "output": {
                        "text": full_text,
                        "tool_calls": tool_calls,
                    },
                    "elapsed_ms": elapsed_ms,
                    "agent": self._card.name,
                },
            )

        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.exception("[%s] A2A stream failed: %s", self._card.name, exc)
            yield A2AStreamChunk(
                id=req.id,
                params={
                    "event": "error",
                    "error": str(exc),
                    "elapsed_ms": elapsed_ms,
                    "agent": self._card.name,
                },
            )
