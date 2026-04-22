from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.signals.sources.kusto_signal_source import KustoSignalSource


MOCK_SR_ROWS = [
    {"OwningServiceName": "Compute", "SRCount": 42, "CreateDate": "2026-04-20T10:00:00Z"},
    {"OwningServiceName": "Storage", "SRCount": 7, "CreateDate": "2026-04-20T10:05:00Z"},
]

MOCK_OUTAGE_ROWS = [
    {
        "OutageId": "OUT-001",
        "ServiceName": "Compute",
        "ImpactStartTime": "2026-04-20T09:30:00Z",
        "Severity": "1",
    },
]


def _make_source(tool_name: str = "query_sr_volume", **kwargs: Any) -> KustoSignalSource:
    defaults = {
        "tool_name": tool_name,
        "params": {"lookback": "1h"},
        "field_mappings": {"service": "OwningServiceName", "count": "SRCount"},
        "source_type": "kusto",
        "signal_type": "sr_volume_spike",
    }
    defaults.update(kwargs)
    return KustoSignalSource(**defaults)


def _mock_mcp_tool(rows: list[dict]) -> MagicMock:
    """Build a mock MCP tool whose call_tool returns JSON with rows."""
    tool = AsyncMock()
    tool.connect = AsyncMock()
    tool.close = AsyncMock()
    tool.call_tool = AsyncMock(return_value=json.dumps({"rows": rows}))
    return tool


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_returns_rows(mock_create: MagicMock) -> None:
    mock_create.return_value = _mock_mcp_tool(MOCK_SR_ROWS)
    source = _make_source()

    rows = await source.fetch_signals({})

    assert len(rows) == 2
    assert rows[0]["OwningServiceName"] == "Compute"
    assert rows[1]["SRCount"] == 7


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_merges_params(mock_create: MagicMock) -> None:
    tool = _mock_mcp_tool(MOCK_SR_ROWS)
    mock_create.return_value = tool
    source = _make_source(params={"lookback": "1h", "bin_size": "5m"})

    await source.fetch_signals({"lookback": "4h"})

    tool.call_tool.assert_awaited_once()
    call_kwargs = tool.call_tool.call_args[1]
    assert call_kwargs["lookback"] == "4h"
    assert call_kwargs["bin_size"] == "5m"


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_passes_tool_name(mock_create: MagicMock) -> None:
    mock_create.return_value = _mock_mcp_tool(MOCK_SR_ROWS)
    source = _make_source(tool_name="query_outages")

    await source.fetch_signals({})

    mock_create.assert_called_once_with("signal_builder", ["query_outages"])


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_empty_rows(mock_create: MagicMock) -> None:
    mock_create.return_value = _mock_mcp_tool([])
    source = _make_source()

    rows = await source.fetch_signals({})

    assert rows == []


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_error_returns_empty(mock_create: MagicMock) -> None:
    tool = AsyncMock()
    tool.connect = AsyncMock()
    tool.close = AsyncMock()
    tool.call_tool = AsyncMock(return_value=json.dumps({"error": "timeout"}))
    mock_create.return_value = tool
    source = _make_source()

    rows = await source.fetch_signals({})

    assert rows == []


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_exception_returns_empty(mock_create: MagicMock) -> None:
    tool = AsyncMock()
    tool.connect = AsyncMock()
    tool.close = AsyncMock()
    tool.call_tool = AsyncMock(side_effect=RuntimeError("connection lost"))
    mock_create.return_value = tool
    source = _make_source()

    rows = await source.fetch_signals({})

    assert rows == []


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_handles_content_objects(mock_create: MagicMock) -> None:
    content = MagicMock()
    content.text = json.dumps({"rows": MOCK_OUTAGE_ROWS})
    tool = AsyncMock()
    tool.connect = AsyncMock()
    tool.close = AsyncMock()
    tool.call_tool = AsyncMock(return_value=[content])
    mock_create.return_value = tool
    source = _make_source(tool_name="query_outages")

    rows = await source.fetch_signals({})

    assert len(rows) == 1
    assert rows[0]["OutageId"] == "OUT-001"


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_closes_tool_on_success(mock_create: MagicMock) -> None:
    tool = _mock_mcp_tool(MOCK_SR_ROWS)
    mock_create.return_value = tool
    source = _make_source()

    await source.fetch_signals({})

    tool.connect.assert_awaited_once()
    tool.close.assert_awaited_once()


@pytest.mark.asyncio
@patch("core.services.signals.sources.kusto_signal_source.create_filtered_mcp_tool")
async def test_fetch_signals_closes_tool_on_error(mock_create: MagicMock) -> None:
    tool = AsyncMock()
    tool.connect = AsyncMock()
    tool.close = AsyncMock()
    tool.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
    mock_create.return_value = tool
    source = _make_source()

    await source.fetch_signals({})

    tool.close.assert_awaited_once()


def test_constructor_stores_fields() -> None:
    source = KustoSignalSource(
        tool_name="my_tool",
        params={"a": "1"},
        field_mappings={"x": "y"},
        source_type="kusto",
        signal_type="test",
    )
    assert source.tool_name == "my_tool"
    assert source.params == {"a": "1"}
    assert source.field_mappings == {"x": "y"}
    assert source.source_type == "kusto"
    assert source.signal_type == "test"
