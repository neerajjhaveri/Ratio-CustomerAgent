"""Config-driven resource registration exposing static JSON/text datasets.

Resources are defined in resources_config.json. To add a new resource:
  1. Drop a data file (JSON or text) in src/datasets/ (or ADLS remote path).
  2. Add an entry to resources_config.json.
No Python code changes required.
"""
from __future__ import annotations
import os, json, logging
from core.mcp_app import mcpserver, LOCAL_DATASETS_DIR, logger
from helper.adls import read_text_file as adls_read_text_file  # remote optional
from helper.mcp_logger import MCPLogger, get_current_xcv, generate_xcv

# Environment variable for remote dataset root path (folder) in ADLS
ENV_DATASET_PATH = "ADLS_RESOURCE_PATH"

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "resources_config.json")

def _load_resource_config() -> list[dict]:
    """Load resource definitions from resources_config.json."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["resources"]


def _can_use_remote() -> bool:
    return os.getenv("USE_REMOTE_FILES", "false").lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Generic loaders (unchanged from original logic)
# ---------------------------------------------------------------------------

def _load_json_dataset(filename: str):
    """Load a JSON dataset, optionally from ADLS if remote enabled."""
    data_text = None
    remote_root = os.getenv(ENV_DATASET_PATH)
    if _can_use_remote() and remote_root:
        remote_path = f"{remote_root.rstrip('/')}/{filename}"
        try:
            logger.info("Attempting remote dataset load: %s", remote_path)
            data_text = adls_read_text_file(remote_path)
        except Exception as e:
            logger.warning("Remote dataset load failed for %s (%s); will try local", remote_path, e)
    if data_text is None:
        local_path = os.path.join(LOCAL_DATASETS_DIR, filename)
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data_text = f.read()
            logger.debug("Loaded local dataset %s", local_path)
        except FileNotFoundError:
            logger.error("Dataset %s not found at %s", filename, local_path)
            return {"error": f"{filename} missing"}
        except Exception as e:
            logger.error("Error reading %s: %s", filename, e, exc_info=True)
            return {"error": str(e)}
    try:
        return json.loads(data_text)
    except Exception as e:
        logger.error("JSON parse error for %s: %s", filename, e, exc_info=True)
        return {"error": f"Failed to parse {filename}: {e}"}


def _load_text_dataset(filename: str) -> str:
    """Load a text dataset, optionally from ADLS if remote enabled."""
    data_text = None
    remote_root = os.getenv(ENV_DATASET_PATH)
    if _can_use_remote() and remote_root:
        remote_path = f"{remote_root.rstrip('/')}/{filename}"
        try:
            logger.info("Attempting remote text dataset load: %s", remote_path)
            data_text = adls_read_text_file(remote_path)
        except Exception as e:
            logger.warning("Remote text dataset load failed for %s (%s); will try local", remote_path, e)
    if data_text is None:
        local_path = os.path.join(LOCAL_DATASETS_DIR, filename)
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data_text = f.read()
            logger.debug("Loaded local text dataset %s", local_path)
        except FileNotFoundError:
            logger.error("Text dataset %s not found at %s", filename, local_path)
            return f"{filename} missing"
        except Exception as e:
            logger.error("Error reading text dataset %s: %s", filename, e, exc_info=True)
            return str(e)
    return data_text


# ---------------------------------------------------------------------------
# Dynamic resource registration from config
# ---------------------------------------------------------------------------

def _register_resources() -> list[str]:
    """Read resources_config.json and register each entry with FastMCP.

    Returns list of registered resource names (used to build __all__).
    """
    entries = _load_resource_config()
    registered: list[str] = []
    for entry in entries:
        rtype = entry.get("type", "json")
        loader = _load_json_dataset if rtype == "json" else _load_text_dataset

        # Factory closure to capture per-resource filename & loader
        def _make_handler(_filename: str, _loader, _name: str):
            def handler():
                result = _loader(_filename)
                # ── MCP Logger ──
                xcv = get_current_xcv() or generate_xcv()
                source = "remote" if _can_use_remote() and os.getenv(ENV_DATASET_PATH) else "local"
                MCPLogger.get_instance().log_resource_served(xcv, _name, source=source)
                return result
            return handler

        handler = _make_handler(entry["filename"], loader, entry["name"])
        handler.__name__ = entry["name"]
        handler.__qualname__ = entry["name"]

        mcpserver.resource(
            entry["uri"],
            name=entry["name"],
            title=entry.get("title", entry["name"]),
            description=entry.get("description", ""),
            mime_type=entry.get("mime_type", "application/json"),
        )(handler)
        registered.append(entry["name"])
    logger.info("Registered %d resources from config: %s", len(registered), registered)
    return registered


_registered_names = _register_resources()

# Expose convenience accessors for synonym resources used by tools.
# These return the data-loading functions (not the data itself) for lazy access.
def _get_resource_loader(name: str):
    """Return the underlying loader function for a named resource."""
    entries = _load_resource_config()
    entry = next((e for e in entries if e["name"] == name), None)
    if entry is None:
        return lambda: {}
    loader = _load_json_dataset if entry.get("type", "json") == "json" else _load_text_dataset
    return lambda: loader(entry["filename"])

servicename_synonyms = _get_resource_loader("servicename_synonyms")
offering_synonyms = _get_resource_loader("offering_synonyms")
region_synonyms = _get_resource_loader("region_synonyms")

__all__ = _registered_names + ["servicename_synonyms", "offering_synonyms", "region_synonyms"]
