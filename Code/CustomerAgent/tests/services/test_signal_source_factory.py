from __future__ import annotations

from typing import Any

import pytest

from core.services.signals.sources.kusto_signal_source import KustoSignalSource
from core.services.signals.sources.signal_source import SignalSource
from core.services.signals.signal_source_factory import SignalSourceFactory


def _kusto_config(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "kusto",
        "tool_name": "query_sr_volume",
        "params": {"lookback": "1h", "bin_size": "5m"},
        "field_mappings": {"service": "OwningServiceName", "count": "SRCount"},
        "source_type": "kusto",
        "signal_type": "sr_volume_spike",
    }
    base.update(overrides)
    return base


def test_create_kusto_source() -> None:
    source = SignalSourceFactory.create(_kusto_config())

    assert isinstance(source, KustoSignalSource)
    assert isinstance(source, SignalSource)


def test_create_sets_tool_name() -> None:
    source = SignalSourceFactory.create(_kusto_config(tool_name="query_outages"))

    assert source.tool_name == "query_outages"


def test_create_sets_params() -> None:
    source = SignalSourceFactory.create(_kusto_config())

    assert source.params == {"lookback": "1h", "bin_size": "5m"}


def test_create_sets_field_mappings() -> None:
    source = SignalSourceFactory.create(_kusto_config())

    assert source.field_mappings == {"service": "OwningServiceName", "count": "SRCount"}


def test_create_sets_source_and_signal_type() -> None:
    source = SignalSourceFactory.create(
        _kusto_config(source_type="kusto", signal_type="outage_declared")
    )

    assert source.source_type == "kusto"
    assert source.signal_type == "outage_declared"


def test_create_defaults_params_to_empty() -> None:
    config = _kusto_config()
    del config["params"]
    source = SignalSourceFactory.create(config)

    assert source.params == {}


def test_create_unknown_type_raises() -> None:
    config = {"type": "rest_api", "tool_name": "x"}

    with pytest.raises(ValueError, match="Unknown signal source type: 'rest_api'"):
        SignalSourceFactory.create(config)


def test_create_none_type_raises() -> None:
    config = {"tool_name": "x"}

    with pytest.raises(ValueError, match="Unknown signal source type: None"):
        SignalSourceFactory.create(config)


def test_create_all_returns_list() -> None:
    configs = [_kusto_config(), _kusto_config(tool_name="query_outages")]
    sources = SignalSourceFactory.create_all(configs)

    assert len(sources) == 2
    assert all(isinstance(s, KustoSignalSource) for s in sources)


def test_create_all_empty_list() -> None:
    sources = SignalSourceFactory.create_all([])

    assert sources == []
