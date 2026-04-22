"""Pydantic interface model for Symptom."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SymptomModel(BaseModel):
    id: str
    template_id: str
    text: str
    category: str
    entities: dict[str, Any] = Field(default_factory=dict)
    source_signal_type: str = ""
    weight: int = 1
    severity: str = ""
    signal_strength: float = 0.0
    confirmed: bool = False
