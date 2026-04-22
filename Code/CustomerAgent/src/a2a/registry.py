"""A2A route registration for MAF agents.

Takes the already-created agents dict from agent_factory and registers
A2A-protocol-compliant routes on the FastAPI app:
  - GET  /a2a/{name}/agent-card   → discovery
  - POST /a2a/{name}/             → invoke agent (A2A JSON-RPC)
  - GET  /a2a/agents              → list all agent cards
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent_framework import Agent
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .agent_card import AgentCard, build_agent_card
from .executor import A2AExecutor
from .schemas import A2AJsonRpcRequest, A2AJsonRpcResponse

logger = logging.getLogger("a2a.registry")


def register_a2a_routes(
    app: FastAPI,
    agents: dict[str, Agent],
    agents_config: list[dict[str, Any]],
    capture_middleware: Any = None,
) -> Dict[str, A2AExecutor]:
    """Register A2A routes for each agent on the FastAPI app.

    Args:
        app: The FastAPI application.
        agents: Dict of agent name → Agent instance (from agent_factory).
        agents_config: The "agents" list from agents_config.json.
        capture_middleware: Shared ToolCallCaptureMiddleware instance.

    Returns:
        Dict of agent name → A2AExecutor for programmatic access.
    """
    executors: Dict[str, A2AExecutor] = {}
    cards: List[dict] = []

    for agent_cfg in agents_config:
        name = agent_cfg["name"]

        # Skip orchestrator — it doesn't make sense as a standalone A2A agent
        if name == "orchestrator":
            continue

        if name not in agents:
            logger.warning("Agent '%s' in config but not in agents dict — skipping A2A registration", name)
            continue

        agent = agents[name]
        prefix = agent_cfg.get("route_prefix", name)

        # Build card and executor
        card = build_agent_card(agent_cfg)
        executor = A2AExecutor(card, agent, capture_middleware)
        executors[name] = executor
        cards.append(card.to_dict())

        # ── GET /a2a/{prefix}/agent-card ─────────────────────
        def _make_card_handler(exec_ref: A2AExecutor):
            async def agent_card_handler():
                return exec_ref.agent_card.to_dict()
            return agent_card_handler

        app.get(f"/a2a/{prefix}/agent-card", tags=["A2A"])(
            _make_card_handler(executor)
        )

        # ── POST /a2a/{prefix}/ ──────────────────────────────
        def _make_invoke_handler(exec_ref: A2AExecutor):
            async def invoke_handler(req: A2AJsonRpcRequest, request: Request):
                if req.method != "message/stream":
                    raise HTTPException(400, "Only 'message/stream' method is supported")

                # Extract user token from headers
                user_token = (
                    request.headers.get("x-user-token")
                    or request.headers.get("X-User-Token")
                )
                if not user_token:
                    auth_header = request.headers.get("authorization", "")
                    if auth_header.lower().startswith("bearer "):
                        user_token = auth_header.split(" ", 1)[1].strip()

                # Execute and collect streaming chunks
                collected = []
                async for chunk in exec_ref.stream(req, user_token=user_token):
                    collected.append(chunk.params)

                # Extract final output from the end event
                final_output = {}
                elapsed_ms = 0
                for p in reversed(collected):
                    if p.get("event") == "end":
                        final_output = p.get("output", {})
                        elapsed_ms = p.get("elapsed_ms", 0)
                        break

                response = A2AJsonRpcResponse(
                    id=req.id,
                    result={
                        "chunks": collected,
                        "output": final_output,
                        "elapsed_ms": elapsed_ms,
                        "agent": exec_ref.agent_card.to_dict(),
                    },
                )
                return JSONResponse(response.model_dump())

            return invoke_handler

        app.post(f"/a2a/{prefix}/", tags=["A2A"])(
            _make_invoke_handler(executor)
        )

        logger.info("Registered A2A routes for '%s' at /a2a/%s/", name, prefix)

    # ── GET /a2a/agents — list all agent cards ───────────────
    @app.get("/a2a/agents", tags=["A2A"])
    async def list_agents():
        return {"agents": cards, "count": len(cards)}

    logger.info("A2A registry: %d agents registered", len(executors))
    return executors
