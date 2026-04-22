"""Core MCP application object and shared directory constants.
Separates FastMCP instance and logging setup from server bootstrap.
"""
from __future__ import annotations
import os, sys, logging
from dotenv import load_dotenv
import warnings
from fastmcp import FastMCP

load_dotenv()

# Silence noisy deprecation from websockets>=14 using legacy shim paths.
# Root cause is upstream dependencies importing websockets.legacy. Safe to ignore.
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"websockets\.legacy"
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"websockets\.server"
)

# Logging configured once here so submodules inherit.
_log_level = os.getenv("LOG_LEVEL", "INFO")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
logging.basicConfig(level=_log_level, handlers=[_handler])
logger = logging.getLogger("ratio_mcp")

# Silence noisy Azure SDK loggers; MCP activity logging is handled by mcp_logger.py.
try:
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.ERROR)
except Exception:
    pass

# FastMCP instance used by prompts/resources/tools modules.
mcpserver = FastMCP(name="ratio_mcp")
logger.info("Initialized FastMCP server 'ratio_mcp'")

# Azure Monitor / App Insights instrumentation
_ai_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
_telemetry_enabled = False
def enable_telemetry() -> bool:
    """Enable Azure Monitor OpenTelemetry if connection string is available.
    Returns True if enabled, False otherwise."""
    global _telemetry_enabled
    if _telemetry_enabled:
        return True
    if not _ai_conn:
        logger.warning("Cannot enable telemetry: APPLICATIONINSIGHTS_CONNECTION_STRING not set.")
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=_ai_conn)
        logger.info("Azure Monitor OpenTelemetry enabled.")
        _telemetry_enabled = True
        return True
    except Exception as e:
        logger.warning("Failed to enable Azure Monitor OpenTelemetry: %s", e)
        return False

def disable_telemetry() -> bool:
    """Disable telemetry by shutting down tracer provider if present. Returns True if shutdown attempted."""
    global _telemetry_enabled
    if not _telemetry_enabled:
        return True
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()  # type: ignore[attr-defined]
            logger.info("Telemetry provider shutdown successful.")
        _telemetry_enabled = False
        return True
    except Exception as e:
        logger.debug("Telemetry disable encountered exception: %s", e)
        return False

# Auto-enable on startup only if env flag TELEMETRY_ENABLED truthy
if os.getenv("TELEMETRY_ENABLED", "true").lower() in ("1", "true", "yes", "on"):
    if _ai_conn:
        enable_telemetry()
    else:
        logger.debug("Telemetry requested but APPLICATIONINSIGHTS_CONNECTION_STRING is absent; staying disabled.")
else:
    logger.info("Telemetry start disabled by TELEMETRY_ENABLED env.")

# Shared directory constants used by multiple modules.
# BASE_DIR points to src/ (parent of core/) so prompts/ and datasets/ paths stay correct.
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOCAL_PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
LOCAL_DATASETS_DIR = os.path.join(BASE_DIR, "datasets")

__all__ = ["mcpserver", "logger", "BASE_DIR", "LOCAL_PROMPTS_DIR", "LOCAL_DATASETS_DIR", "enable_telemetry", "disable_telemetry"]
