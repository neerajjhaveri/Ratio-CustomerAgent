"""Factory for creating SignalSource instances from config dicts."""
from __future__ import annotations

from typing import Any

from .sources.kusto_signal_source import KustoSignalSource
from .sources.signal_source import SignalSource


class SignalSourceFactory:

    @staticmethod
    def create(config: dict[str, Any]) -> SignalSource:
        source_type = config.get("type")
        if source_type == "kusto":
            return KustoSignalSource(
                tool_name=config["tool_name"],
                params=config.get("params", {}),
                field_mappings=config.get("field_mappings", {}),
                source_type=config.get("source_type", ""),
                signal_type=config.get("signal_type", ""),
            )
        raise ValueError(f"Unknown signal source type: {source_type!r}")

    @staticmethod
    def create_all(configs: list[dict[str, Any]]) -> list[SignalSource]:
        return [SignalSourceFactory.create(c) for c in configs]
