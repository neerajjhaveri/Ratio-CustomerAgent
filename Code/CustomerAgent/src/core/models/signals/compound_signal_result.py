"""Pydantic interface model for CompoundSignalResult."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CompoundSignalResultModel(BaseModel):
    compound_id: str
    compound_name: str
    activated: bool
    confidence: str
    strength: float
    raw_strength: float = 0.0
    contributing_types: list[str] = Field(default_factory=list)
    rationale: str = ""
