"""Config-driven prompt registration and composition logic.

Prompts are defined in prompts_config.json. To add a new prompt:
  1. Drop a .txt template file in src/prompts/ (or ADLS remote path).
  2. Add an entry to prompts_config.json.
No Python code changes required.
"""
from __future__ import annotations
import os, json, logging
from functools import lru_cache
from core.mcp_app import mcpserver, LOCAL_PROMPTS_DIR, LOCAL_DATASETS_DIR, logger
from helper.adls import read_text_file as adls_read_text_file
from helper.mcp_logger import MCPLogger, get_current_xcv, generate_xcv

# Environment variable names for ADLS remote storage (all optional for fallback)
ENV_PROMPT_PATH = "ADLS_PROMPT_PATH"
ENV_SCHEMA_PATH = "ADLS_SCHEMA_PATH"
TOKEN = "{database_schema}"
SCHEMA_FILENAME = "DatabaseSchema.txt"

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "prompts_config.json")

def _load_prompt_config() -> list[dict]:
    """Load prompt definitions from prompts_config.json."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["prompts"]


# ---------------------------------------------------------------------------
# Helpers (unchanged from original logic)
# ---------------------------------------------------------------------------

def _read_local(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.debug("Local file not found: %s", path)
    except OSError as e:
        logger.warning("Error reading local file %s: %s", path, e)
    return None


def _can_use_remote() -> bool:
    return os.getenv("USE_REMOTE_FILES", "false").lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=16)
def _load_schema() -> str:
    text: str | None = None
    remote_path = os.getenv(ENV_SCHEMA_PATH)
    if _can_use_remote() and remote_path:
        try:
            logger.info("Loading schema from ADLS: %s", remote_path)
            text = adls_read_text_file(remote_path)
        except Exception as e:
            logger.warning("Remote schema load failed (%s); will try local fallback", e)
    if text is None:
        local_path = os.path.join(LOCAL_DATASETS_DIR, SCHEMA_FILENAME)
        text = _read_local(local_path) or "(Schema unavailable)"
    return text.strip()


@lru_cache(maxsize=32)
def _compose_prompt(name: str) -> str:
    """Compose prompt text for *name* by looking up its filename in the config."""
    # Build lookup from config so _compose_prompt stays usable by api_routes
    entries = _load_prompt_config()
    entry = next((e for e in entries if e["name"] == name), None)
    if entry is None:
        raise ValueError(f"Unknown prompt name '{name}'")
    filename = entry["filename"]
    inject = entry.get("inject_schema", False)

    template: str | None = None
    remote_prompt_path = os.getenv(ENV_PROMPT_PATH) + f"/{filename}" if os.getenv(ENV_PROMPT_PATH) else None
    if _can_use_remote() and remote_prompt_path:
        try:
            logger.info("Loading prompt '%s' from ADLS path: %s", name, remote_prompt_path)
            template = adls_read_text_file(remote_prompt_path)
        except Exception as e:
            logger.warning("Remote prompt load failed (%s); will try local fallback", e)
    if template is None:
        local_path = os.path.join(LOCAL_PROMPTS_DIR, filename)
        template = _read_local(local_path)
        logger.info("Loading prompt '%s' from local path: %s", name, local_path)
        if template is None:
            logger.error("Prompt template missing for '%s' at %s", name, local_path)
            template = f"(Prompt template '{filename}' not found)"
    if inject and TOKEN in template:
        try:
            template = template.replace(TOKEN, _load_schema())
        except Exception as e:
            logger.error("Schema injection failed for prompt '%s': %s", name, e, exc_info=True)
            template = template.replace(TOKEN, "(Schema unavailable \u2014 load error)")
    return template


def _prompt_response(name: str) -> str:
    """Return prompt text as a plain string; FastMCP wraps it in UserMessage internally."""
    try:
        text = _compose_prompt(name)
    except Exception as e:
        logger.error("Failed to compose prompt '%s': %s", name, e, exc_info=True)
        raise
    logger.info("Returning %s (length=%d)", name, len(text))
    # ── MCP Logger ──
    xcv = get_current_xcv() or generate_xcv()
    MCPLogger.get_instance().log_prompt_served(xcv, name, length=len(text))
    return text


# ---------------------------------------------------------------------------
# Dynamic prompt registration from config
# ---------------------------------------------------------------------------

def _register_prompts() -> list[str]:
    """Read prompts_config.json and register each entry with FastMCP.

    Returns list of registered prompt names (used to build __all__).
    """
    entries = _load_prompt_config()
    registered: list[str] = []
    for entry in entries:
        name = entry["name"]
        desc = entry.get("description", "")

        # Factory closure to capture per-prompt name
        def _make_handler(_name: str, _desc: str):
            def handler() -> str:
                return _prompt_response(_name)
            handler.__name__ = _name
            handler.__qualname__ = _name
            handler.__doc__ = _desc
            return handler

        mcpserver.prompt()(_make_handler(name, desc))
        registered.append(name)
    logger.info("Registered %d prompts from config: %s", len(registered), registered)
    return registered


_registered_names = _register_prompts()

__all__ = _registered_names + ["_compose_prompt"]
