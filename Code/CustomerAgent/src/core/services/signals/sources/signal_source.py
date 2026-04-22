"""Abstract base class for signal data sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SignalSource(ABC):
    """Abstract base for all signal sources."""

    @abstractmethod
    async def fetch_signals(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        ...
