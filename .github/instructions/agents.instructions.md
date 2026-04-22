---
applyTo: Code/Servers/agents/**
---

# Agent Service Instructions

## Service Context
- FastAPI service at `Code/Servers/agents/` running on port 8000
- Microsoft Agent Framework v1.0.1 for agent orchestration
- Entry point: `app_kernel.py` (FastAPI app) and `devui_serve.py` (DevUI)

## Architecture
- `agents/` — One class per agent, each extending `BaseAgent` and registered via `@register_agent`
  - `base_agent.py` — `BaseAgent` class (name, instructions, tools)
  - `agent_factory.py` — Registry, auto-discovery, `get_agent_configs()`
  - `*_agent.py` — Individual agent definitions (one per file)
- `tools/` — `@tool` functions callable by agents (e.g., `kusto_tools.py`, `general_tools.py`)
- `workflows/` — Multi-agent orchestration patterns (`workflows.py`)
- `providers/` — Agent runtime: chat client, sessions, memory, middleware (`af_provider.py`)
- `app_config.py` — Service configuration (reads env vars)
- `app_kernel.py` — FastAPI app with all routes

## Import Rules
- Service-local: `from tools.kusto_tools import ALL_KUSTO_TOOLS` ✅
- Shared: `from Code.Shared.middleware import build_default_middleware` ✅
- Never: `from Code.Servers.agents.tools.kusto_tools import ...` ❌

## Agent Framework Patterns
- Use `@tool` decorator (not `@kernel_function`)
- Use `Agent()` with `client=`, `name=`, `instructions=`, `tools=`, `middleware=`
- Use `AgentSession` for multi-turn conversations
- Use `FoundryChatClient` from `Code.Shared.clients.chat_client`
- Use `build_default_middleware()` from `Code.Shared.middleware`
- DevUI: `devui_serve.py` starts the visual debugging UI on port 8090

## Tools
- Every tool function must have a clear docstring (LLM reads it)
- Tools return strings
- Export as `ALL_<NAME>_TOOLS = [tool1, tool2]` list
- Import in the agent file that uses them (e.g., `from tools.kusto_tools import ALL_KUSTO_TOOLS`)

## Adding a New Agent
1. Create `agents/<name>_agent.py` — extend `BaseAgent`, use `@register_agent`
2. Add import to `agents/agent_factory.py` → `_discover_agents()`
3. The agent is auto-available on all API endpoints
- Naming: `PascalCase` class, `snake_case` file
- Tools: import with `try/except ImportError` fallback
- Instructions: clear, specific — the LLM reads them for routing
