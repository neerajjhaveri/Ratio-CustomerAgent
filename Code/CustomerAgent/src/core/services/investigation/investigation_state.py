"""Data models for the investigation lifecycle.

This module re-exports the canonical Pydantic models from core.models
under their short names for backward compatibility. All consumers can
continue to use::

    from .investigation_state import Symptom, Hypothesis, Investigation

The actual class definitions live in:
    core.models.enums          — InvestigationPhase, HypothesisStatus, EvidenceVerdict, SymptomVerdict
    core.models.symptoms       — SymptomModel (aliased as Symptom)
    core.models.hypothesis     — HypothesisModel, EvidenceItemModel, EvidenceRequirementModel,
                                 InvestigationContextModel, StreamEventModel
    core.models.investigationModel — InvestigationModel (aliased as Investigation)
"""
from __future__ import annotations

# ── Enums (re-export) ────────────────────────────────────────────
from core.models.enums import (  # noqa: F401
    EvidenceVerdict,
    HypothesisStatus,
    InvestigationPhase,
    SymptomVerdict,
)

# ── Domain models (re-export under short names) ──────────────────
from core.models.investigation.symptoms import SymptomModel as Symptom  # noqa: F401
from core.models.investigation.hypothesis import HypothesisModel as Hypothesis  # noqa: F401
from core.models.investigation.evidence_item import EvidenceItemModel as EvidenceItem  # noqa: F401
from core.models.investigation.evidence_requirement import EvidenceRequirementModel as EvidenceRequirement  # noqa: F401
from core.models.investigation.investigation_context import InvestigationContextModel as InvestigationContext  # noqa: F401
from core.models.investigation.stream_event import StreamEventModel as StreamEvent  # noqa: F401
from core.models.investigation.investigationModel import InvestigationModel as Investigation  # noqa: F401
