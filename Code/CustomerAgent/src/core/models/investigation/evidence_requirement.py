"""Pydantic interface model for EvidenceRequirement."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceRequirementModel(BaseModel):
    er_id: str
    description: str
    technology_tag: str
    tool_name: str
    parameters: dict[str, str] = Field(default_factory=dict)
    hypothesis_ids: list[str] = Field(default_factory=list)
    status: str = "pending"
