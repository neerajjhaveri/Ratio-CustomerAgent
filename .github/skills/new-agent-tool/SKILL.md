# Skill: Add a New Agent Tool

## When to Use

Use this skill when asked to add a new `@tool` function that agents can call — e.g., a new data source query, external API call, or computation.

## Steps

### 1. Create the tool file

Create `Code/Servers/agents/tools/<name>_tools.py`:

```python
"""<Name> tools for agent use."""
import logging
from agent_framework import tool

logger = logging.getLogger(__name__)


@tool
def <tool_name>(<param>: str) -> str:
    """<Clear description of what this tool does — the LLM reads this for tool selection.>

    Args:
        <param>: <Description of the parameter>

    Returns:
        <Description of what is returned>
    """
    logger.info("Calling <tool_name> with %s", <param>)
    # Implementation here
    result = ...
    return str(result)


# Export list for registration
ALL_<NAME>_TOOLS = [<tool_name>]
```

### 2. Register the tool in the provider

Edit `Code/Servers/agents/providers/af_provider.py`:

```python
# Add import (with graceful fallback)
try:
    from tools.<name>_tools import ALL_<NAME>_TOOLS
except ImportError:
    ALL_<NAME>_TOOLS = []

# Add to the tools list where agents are created
tools = [*ALL_KUSTO_TOOLS, *ALL_<NAME>_TOOLS]
```

### 3. Add tests

Create `Code/Servers/agents/tools/test_<name>_tools.py`:

```python
import pytest
from tools.<name>_tools import <tool_name>

def test_<tool_name>_returns_string():
    result = <tool_name>("test_input")
    assert isinstance(result, str)

def test_<tool_name>_handles_empty_input():
    result = <tool_name>("")
    assert result is not None
```

## Rules

- **Always use the `@tool` decorator** from `agent_framework` (not `@kernel_function`)
- **Write a clear docstring** — the LLM uses it for tool selection; vague descriptions = wrong tool calls
- **Return strings** — agent tools should return string results (the LLM processes text)
- **Log calls** — use `logger.info()` at the start of every tool function
- **Graceful imports** — wrap the import in the provider with `try/except ImportError`
- **No blocking I/O** — if the tool calls external services, use async patterns or `run_in_threadpool()`
- **Guard secrets** — never hardcode API keys; read from config via `Code.Shared.config.settings`
