"""Shared enums for the investigation lifecycle.

Extracted from core.services.investigation.investigation_state so they can be
imported by both the domain dataclasses and the Pydantic interface models
without circular dependencies.
"""
from __future__ import annotations

import enum


class InvestigationPhase(str, enum.Enum):
    """Investigation lifecycle phases.

    Sequence: initializing → triage → hypothesizing → planning → collecting
              → reasoning → acting → notifying → complete

    Cycle support: reasoning can backtrack to planning when needs_more_evidence
    is signaled (max _MAX_EVIDENCE_CYCLES times).
    """
    INITIALIZING = "initializing"
    TRIAGE = "triage"
    HYPOTHESIZING = "hypothesizing"
    PLANNING = "planning"
    COLLECTING = "collecting"
    REASONING = "reasoning"
    ACTING = "acting"
    NOTIFYING = "notifying"
    COMPLETE = "complete"


class HypothesisStatus(str, enum.Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    CONTRIBUTING = "resolved_as_contributing"


class EvidenceVerdict(str, enum.Enum):
    STRONGLY_SUPPORTS = "strongly_supports"
    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    INCONCLUSIVE = "inconclusive"
    REFUTES = "refutes"
    STRONGLY_REFUTES = "strongly_refutes"


class SymptomVerdict(str, enum.Enum):
    """Per-symptom verdict assigned by the reasoner for a specific hypothesis."""
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    INCONCLUSIVE = "inconclusive"
