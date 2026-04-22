"""Pydantic interface model for StreamEvent."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StreamEventModel(BaseModel):
    """Event streamed to the UI via SSE."""
    event_type: str
    agent_name: str = ""
    phase: str = ""
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=_utc_now_iso)
