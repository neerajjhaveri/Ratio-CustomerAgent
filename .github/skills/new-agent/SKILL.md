# Skill: Create a New Agent Framework Agent

## When to Use

Use this skill when asked to create a new agent — a specialist AI persona with its own instructions and optional tools that participates in single-agent chat or multi-agent orchestrations.

## Steps

### 1. Create the agent file

Create `Code/Servers/agents/agents/<name>_agent.py`:

```python
"""<Name> Agent — <one-line description of role>."""
import logging

from agents.base_agent import BaseAgent
from agents.agent_factory import register_agent

logger = logging.getLogger(__name__)

# Import tools (with graceful fallback for optional dependencies)
try:
    from tools.<name>_tools import ALL_<NAME>_TOOLS
except ImportError:
    logger.warning("<name>_tools not available — <Name> Agent will have no tools")
    ALL_<NAME>_TOOLS = []


@register_agent
class <Name>Agent(BaseAgent):
    name = "<Name>_Agent"
    instructions = (
        "You are the <Name> Agent. <Describe the agent's role, capabilities, "
        "and how it should behave. Be specific — the LLM reads this to understand "
        "what this agent does and when to use it.>"
    )
    tools = ALL_<NAME>_TOOLS
```

If the agent has **no tools**, simplify:

```python
"""<Name> Agent — <one-line description>."""
from agents.base_agent import BaseAgent
from agents.agent_factory import register_agent


@register_agent
class <Name>Agent(BaseAgent):
    name = "<Name>_Agent"
    instructions = (
        "You are the <Name> Agent. <Role description.>"
    )
    tools = []
```

### 2. Register in the factory

Edit `Code/Servers/agents/agents/agent_factory.py` — add an import to `_discover_agents()`:

```python
def _discover_agents() -> None:
    """Import all agent modules to trigger registration."""
    from agents.manager_agent import ManagerAgent  # noqa: F401
    from agents.planner_agent import PlannerAgent  # noqa: F401
    from agents.generic_agent import GenericAgent  # noqa: F401
    from agents.data_analyst_agent import DataAnalystAgent  # noqa: F401
    from agents.human_agent import HumanAgent  # noqa: F401
    from agents.<name>_agent import <Name>Agent  # noqa: F401  # ← ADD THIS
```

### 3. Create tools (if the agent needs them)

If the agent requires new `@tool` functions, follow the **new-agent-tool** skill to create `tools/<name>_tools.py`. If the agent reuses existing tools (e.g., `ALL_KUSTO_TOOLS`), import them directly.

### 4. Add tests

Create `Code/Servers/agents/agents/test_<name>_agent.py`:

```python
import pytest
from agents.<name>_agent import <Name>Agent
from agents.base_agent import BaseAgent


def test_<name>_agent_is_registered():
    from agents.agent_factory import get_agent_configs
    configs = get_agent_configs()
    assert "<Name>_Agent" in configs


def test_<name>_agent_extends_base():
    assert issubclass(<Name>Agent, BaseAgent)


def test_<name>_agent_has_name():
    assert <Name>Agent.name == "<Name>_Agent"


def test_<name>_agent_has_instructions():
    assert len(<Name>Agent.instructions) > 0


def test_<name>_agent_config_format():
    cfg = <Name>Agent.get_config()
    assert "instructions" in cfg
    assert "tools" in cfg
    assert isinstance(cfg["tools"], list)
```

### 5. Verify

The agent is automatically available on all API endpoints once registered:

- `GET /api/af/agents` — lists the new agent
- `POST /api/af/chat` — chat with it via `{"agent_name": "<Name>_Agent", "message": "..."}`
- `POST /api/af/orchestrations/run` — include it in multi-agent workflows
- DevUI at `http://127.0.0.1:8090` — appears as a testable entity

No changes to `app_kernel.py`, `af_provider.py`, or `workflows.py` are needed.

## Architecture Reference

```
agents/
├── base_agent.py          # BaseAgent class — extend this
├── agent_factory.py       # Registry + auto-discovery — register here
├── manager_agent.py       # Example: no tools
├── generic_agent.py       # Example: with tools
├── data_analyst_agent.py  # Example: with graceful tool import
└── <name>_agent.py        # YOUR NEW AGENT
```

**How it works:**

1. `@register_agent` decorator adds the class to the factory registry at import time
2. `_discover_agents()` in `agent_factory.py` imports all agent modules on startup
3. `af_provider.py` calls `get_agent_configs()` to load all registered agents
4. `create_agent()` in `af_provider.py` builds Agent Framework `Agent` instances at runtime with the chat client, context providers, and middleware

## Rules

- **One file per agent** — `agents/<name>_agent.py`
- **Use `@register_agent` decorator** — this is what adds the agent to the factory
- **Class naming** — `PascalCase` class, `snake_case` file (e.g., `DataAnalystAgent` in `data_analyst_agent.py`)
- **Agent name convention** — `<Name>_Agent` with underscores (e.g., `Data_Analyst_Agent`)
- **Instructions are critical** — the LLM reads them to understand the agent's role; be clear, specific, and actionable
- **Tools are optional** — agents without tools set `tools = []`
- **Graceful tool imports** — always wrap external tool imports in `try/except ImportError`
- **No runtime logic in agent files** — agent files are config containers only; runtime behavior lives in `af_provider.py`
- **Logging** — use `logging.getLogger(__name__)`, never `print()`
- **Import style** — service-local absolute imports only (`from agents.base_agent import BaseAgent`)
