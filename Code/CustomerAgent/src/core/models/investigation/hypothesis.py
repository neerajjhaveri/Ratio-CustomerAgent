"""Pydantic interface model for Hypothesis."""
from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.enums import EvidenceVerdict, HypothesisStatus, SymptomVerdict  # noqa: E501


class HypothesisModel(BaseModel):
    id: str
    template_id: str
    statement: str
    category: str
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    confidence: float = 0.0
    expected_symptoms: list[str] = Field(default_factory=list)
    matched_symptoms: list[str] = Field(default_factory=list)
    match_score: float = 0.0
    min_symptoms_for_match: int = 2
    evidence_needed: list[str] = Field(default_factory=list)
    evidence_collected: list[str] = Field(default_factory=list)
    evidence_delta: list[str] = Field(default_factory=list)
    verdicts: dict[str, EvidenceVerdict] = Field(default_factory=dict)
    symptom_verdicts: dict[str, SymptomVerdict] = Field(default_factory=dict)
    determination: str = ""
