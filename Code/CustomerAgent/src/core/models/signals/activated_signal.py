"""Pydantic interface model for ActivatedSignal."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivatedSignalModel(BaseModel):
    signal_type_id: str
    signal_name: str
    granularity: str
    confidence: str
    strength: float
    raw_strength: float = 0.0
    activation_summary: str = ""
    matched_row_count: int = 0
    timestamp: datetime
