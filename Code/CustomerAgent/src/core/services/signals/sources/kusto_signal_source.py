"""KustoSignalSource – fetches signal data via MCP collection tools."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from core.mcp_integration import create_filtered_mcp_tool
from .signal_source import SignalSource

logger = logging.getLogger(__name__)


class KustoSignalSource(SignalSource):
    """Signal source that calls MCP collection tools to retrieve Kusto data.

    Replaces direct Kusto SDK calls with MCP tool invocations, matching
    the pattern previously used by ``signal_builder._call_collection_tool()``.
    """

    def __init__(
        self,
        tool_name: str,
        params: dict[str, str],
        field_mappings: dict[str, str],
        source_type: str,
        signal_type: str,
    ) -> None:
        self.tool_name = tool_name
        self.params = params
        self.field_mappings = field_mappings
        self.source_type = source_type
        self.signal_type = signal_type

    async def fetch_signals(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Call the MCP collection tool and return parsed rows.

        ``params`` are merged on top of ``self.params`` so callers can
        override context-specific values at call time.
        """
        merged_params = {**self.params, **params}
        mcp_tool = create_filtered_mcp_tool("signal_builder", [self.tool_name])
        t0 = time.monotonic()
        try:
            await mcp_tool.connect()
            try:
                result = await mcp_tool.call_tool(self.tool_name, **merged_params)
            finally:
                await mcp_tool.close()

            # result is either str or list[Content]
            if isinstance(result, list):
                text = "".join(c.text for c in result if hasattr(c, "text"))
            else:
                text = str(result)

            parsed = json.loads(text)
            if "error" in parsed:
                elapsed = round((time.monotonic() - t0) * 1000, 1)
                logger.warning(
                    "MCP tool %s returned error (%.1fms): %s",
                    self.tool_name, elapsed, parsed["error"],
                )
                return []

            rows = parsed.get("rows", [])
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.info(
                "KustoSignalSource[%s] fetched %d rows in %.1fms",
                self.tool_name, len(rows), elapsed,
            )
            return rows

        except Exception:
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.exception(
                "KustoSignalSource[%s] failed after %.1fms",
                self.tool_name, elapsed,
            )
            return []
