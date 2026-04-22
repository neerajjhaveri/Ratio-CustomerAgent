"""Pydantic interface model for TypeSignalResult."""
from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.signals.activated_signal import ActivatedSignalModel


class TypeSignalResultModel(BaseModel):
    signal_type_id: str
    signal_name: str
    has_data: bool
    row_count: int
    max_strength: float = 0.0
    raw_max_strength: float = 0.0
    best_confidence: str = "Low"
    activated_granularities: list[ActivatedSignalModel] = Field(default_factory=list)
