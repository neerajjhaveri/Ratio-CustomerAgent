"""
Config-driven MAF Agent factory.

Creates Agent instances from agents_config.json. Each agent gets:
  - A shared AzureOpenAIChatClient
  - Instructions loaded from its prompt file
  - MCP tools filtered by tool_mode (none / filtered / all)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from agent_framework import Agent
from agent_framework.openai import OpenAIChatOptions

from .middleware.tool_capture_middleware import ToolCallCaptureMiddleware
from .middleware.eval_middleware import OutputEvaluationMiddleware, EVAL_ENABLED
from .middleware.prompt_injection_middleware import PromptInjectionMiddleware, INJECTION_ENABLED
from .middleware.llm_logging_middleware import LLMLoggingMiddleware, LLM_LOGGING_ENABLED
from .mcp_integration import create_filtered_mcp_tool, create_mcp_tool
from .prompt_loader import load_all_prompts

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config"))


def load_config() -> dict[str, Any]:
    """Load agents_config.json."""
    path = os.path.join(_CONFIG_DIR, "agents", "agents_config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def create_agents(
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Agent], ToolCallCaptureMiddleware, OutputEvaluationMiddleware]:
    """Create all MAF Agent instances from config.

    Args:
        config: Parsed agents_config.json dict. If None, loads from disk.

    Returns:
        Tuple of (agent name → Agent instance dict, shared capture middleware, eval middleware).
    """
    if config is None:
        config = load_config()

    # ── Create chat clients (shared default + per-agent overrides) ──
    from helper.llm import create_chat_client
    default_client = create_chat_client()
    _client_cache: dict[str, Any] = {}  # model name → client, avoids duplicates

    # ── Load prompts ─────────────────────────────────────────
    agents_cfg = config["agents"]
    prompts = load_all_prompts(agents_cfg)

    # ── Create shared MCP tool (for "all" mode agents) ───────
    shared_mcp: Any = None  # lazy-created if needed

    # ── Shared middleware for tool-call capture ───────────────
    capture_middleware = ToolCallCaptureMiddleware()

    # ── Shared middleware for output evaluation ───────────────
    eval_middleware = OutputEvaluationMiddleware() if EVAL_ENABLED else None

    # ── Shared middleware for prompt injection detection ──────
    injection_middleware = PromptInjectionMiddleware() if INJECTION_ENABLED else None

    # ── Shared middleware for LLM call logging ────────────────
    # A sentinel instance used for drain()/reset() calls.
    # Per-agent instances (with agent_name) are created in the loop below.
    llm_logging_sentinel = LLMLoggingMiddleware() if LLM_LOGGING_ENABLED else None

    # ── Build agents ─────────────────────────────────────────
    agents: dict[str, Agent] = {}

    for agent_cfg in agents_cfg:
        name = agent_cfg["name"]
        description = agent_cfg.get("description", "")
        instructions = prompts.get(name, f"You are {name}.")
        tool_mode = agent_cfg.get("tool_mode", "none")
        mcp_tools_list = agent_cfg.get("mcp_tools", [])

        # ── Resolve LLM client (per-agent model or shared default) ──
        agent_model = agent_cfg.get("model")
        if agent_model:
            if agent_model not in _client_cache:
                _client_cache[agent_model] = create_chat_client(model=agent_model)
                logger.info("Created LLM client for model '%s'", agent_model)
            client = _client_cache[agent_model]
        else:
            client = default_client

        # ── Build tools list based on tool_mode ──────────────
        tools: list = []

        if tool_mode == "none":
            pass  # orchestrator, summarizer, visualizer — no tools

        elif tool_mode == "filtered" and mcp_tools_list:
            mcp_tool = create_filtered_mcp_tool(name, mcp_tools_list)
            tools.append(mcp_tool)

        elif tool_mode == "all":
            if shared_mcp is None:
                shared_mcp = create_mcp_tool(name="ratio-mcp-shared")
            tools.append(shared_mcp)

        # ── Create Agent ─────────────────────────────────────
        # Agents with tools get function-level capture middleware;
        # agents with "evaluate": true also get eval middleware (if globally enabled);
        # agents with "prompt_injection": true get injection detection (if globally enabled).
        agent_eval = agent_cfg.get("evaluate", False)
        agent_shield = agent_cfg.get("prompt_injection", False)
        agent_llm_log = agent_cfg.get("llm_logging", True)

        # Build middleware list: shield first (pre-execution), capture, eval last (post-execution)
        mw_list = []
        if injection_middleware and agent_shield:
            mw_list.append(injection_middleware)
        if tools:
            mw_list.append(capture_middleware)
        if eval_middleware and agent_eval:
            mw_list.append(eval_middleware)
        if llm_logging_sentinel and agent_llm_log:
            mw_list.append(LLMLoggingMiddleware(agent_name=name))

        # ── Build default_options from config (temperature, etc.) ──
        default_options = None
        temperature = agent_cfg.get("temperature")
        if temperature is not None:
            default_options = OpenAIChatOptions(temperature=temperature)

        # GroupChat AgentExecutor manages conversation context via its cache;
        # per-service-call history persistence can cause orphaned tool_calls
        # when a tool execution partially fails between API calls.
        history_persistence = agent_cfg.get("history_persistence", False)

        agent = Agent(
            client=client,
            name=name,
            description=description,
            instructions=instructions,
            tools=tools if tools else None,
            default_options=default_options,
            middleware=mw_list if mw_list else None,
            require_per_service_call_history_persistence=history_persistence,
        )

        agents[name] = agent
        logger.info(
            "Created agent '%s' (tool_mode=%s, tools=%s)",
            name, tool_mode, [t for t in mcp_tools_list] if mcp_tools_list else "none",
        )

    logger.info("Created %d agents: %s", len(agents), list(agents.keys()))

    # ── Wire up agent_tools (as_tool) for coordinator-style agents ────
    for agent_cfg in agents_cfg:
        if agent_cfg.get("tool_mode") != "agent_tools":
            continue

        name = agent_cfg["name"]
        sub_agent_names = agent_cfg.get("sub_agents", [])
        if not sub_agent_names:
            logger.warning("agent_tools agent '%s' has no sub_agents configured", name)
            continue

        # Convert sub-agents into FunctionTools via as_tool()
        agent_tools = []
        for sub_name in sub_agent_names:
            sub_agent = agents.get(sub_name)
            if sub_agent is None:
                logger.warning("Sub-agent '%s' not found for '%s'", sub_name, name)
                continue
            tool = sub_agent.as_tool(
                name=sub_name,
                description=sub_agent.description or f"Run {sub_name} agent",
                arg_name="task",
                arg_description="The enriched user query for this analyst",
                propagate_session=False,
            )
            agent_tools.append(tool)
            logger.info("Attached sub-agent '%s' as tool to '%s'", sub_name, name)

        if agent_tools:
            # Recreate the coordinator agent with the sub-agent tools
            coordinator = agents[name]
            coord_model = agent_cfg.get("model")
            coord_client = _client_cache[coord_model] if coord_model and coord_model in _client_cache else default_client
            coord_eval = agent_cfg.get("evaluate", False)
            coord_shield = agent_cfg.get("prompt_injection", False)
            coord_llm_log = agent_cfg.get("llm_logging", True)
            coord_temp = agent_cfg.get("temperature")
            coord_options = OpenAIChatOptions(temperature=coord_temp) if coord_temp is not None else None
            coord_mw = []
            if injection_middleware and coord_shield:
                coord_mw.append(injection_middleware)
            coord_mw.append(capture_middleware)
            if eval_middleware and coord_eval:
                coord_mw.append(eval_middleware)
            if llm_logging_sentinel and coord_llm_log:
                coord_mw.append(LLMLoggingMiddleware(agent_name=name))
            coord_history = agent_cfg.get("history_persistence", False)
            agents[name] = Agent(
                client=coord_client,
                name=name,
                description=coordinator.description,
                instructions=prompts.get(name, f"You are {name}."),
                tools=agent_tools,
                default_options=coord_options,
                middleware=coord_mw,
                require_per_service_call_history_persistence=coord_history,
            )
            logger.info(
                "Re-created agent '%s' with %d sub-agent tools: %s",
                name, len(agent_tools), sub_agent_names,
            )

    return agents, capture_middleware, eval_middleware, injection_middleware, llm_logging_sentinel, prompts