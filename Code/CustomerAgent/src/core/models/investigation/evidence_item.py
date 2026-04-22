"""Pydantic interface model for EvidenceItem."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from core.models.enums import EvidenceVerdict  # noqa: E501


class EvidenceItemModel(BaseModel):
    id: str
    er_id: str
    hypothesis_ids: list[str]
    agent_name: str
    tool_name: str
    raw_data: Any = None
    summary: str = ""
    preliminary_verdict: str = ""
    final_verdict: EvidenceVerdict | None = None
    collected_at: str = ""
