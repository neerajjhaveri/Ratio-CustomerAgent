"""Tests for investigation Pydantic models."""
from __future__ import annotations

import pytest

from core.models.enums import (
    EvidenceVerdict,
    HypothesisStatus,
    InvestigationPhase,
    SymptomVerdict,
)
from core.models.investigation.symptoms import SymptomModel
from core.models.investigation.hypothesis import HypothesisModel
from core.models.investigation.evidence_item import EvidenceItemModel
from core.models.investigation.evidence_requirement import EvidenceRequirementModel
from core.models.investigation.investigation_context import InvestigationContextModel
from core.models.investigation.stream_event import StreamEventModel
from core.models.investigation.investigationModel import InvestigationModel


# ── SymptomModel ─────────────────────────────────────────────────

def test_symptom_required_fields() -> None:
    s = SymptomModel(id="S1", template_id="SYM-SLI-001", text="breach detected", category="sli")
    assert s.id == "S1"
    assert s.confirmed is False
    assert s.weight == 1


def test_symptom_all_fields() -> None:
    s = SymptomModel(
        id="S2", template_id="SYM-OUT-001", text="outage", category="outage",
        source_signal_type="SIG-TYPE-3", weight=3, severity="HIGH",
        signal_strength=4.2, confirmed=True, entities={"region": "eastus"},
    )
    assert s.severity == "HIGH"
    assert s.signal_strength == 4.2
    assert s.entities["region"] == "eastus"


# ── HypothesisModel ─────────────────────────────────────────────

def test_hypothesis_defaults() -> None:
    h = HypothesisModel(id="H1", template_id="HYP-SLI-001", statement="test", category="sli")
    assert h.status == HypothesisStatus.ACTIVE
    assert h.confidence == 0.0
    assert h.match_score == 0.0
    assert h.expected_symptoms == []
    assert h.verdicts == {}


def test_hypothesis_status_mutation() -> None:
    h = HypothesisModel(id="H1", template_id="T", statement="s", category="c")
    h.status = HypothesisStatus.CONFIRMED
    assert h.status == HypothesisStatus.CONFIRMED


def test_hypothesis_verdict_assignment() -> None:
    h = HypothesisModel(id="H1", template_id="T", statement="s", category="c")
    h.verdicts["ER-001"] = EvidenceVerdict.SUPPORTS
    h.symptom_verdicts["SYM-001"] = SymptomVerdict.SATISFIED
    assert h.verdicts["ER-001"] == EvidenceVerdict.SUPPORTS
    assert h.symptom_verdicts["SYM-001"] == SymptomVerdict.SATISFIED


# ── EvidenceItemModel ────────────────────────────────────────────

def test_evidence_item_required_fields() -> None:
    ei = EvidenceItemModel(
        id="E1", er_id="ER-001", hypothesis_ids=["H1"],
        agent_name="sli_collector", tool_name="collect_impacted_resource_customer_tool",
    )
    assert ei.summary == ""
    assert ei.final_verdict is None


# ── EvidenceRequirementModel ─────────────────────────────────────

def test_evidence_requirement_defaults() -> None:
    er = EvidenceRequirementModel(
        er_id="ER-001", description="SLI data",
        technology_tag="kusto", tool_name="collect_impacted_resource_customer_tool",
    )
    assert er.status == "pending"
    assert er.hypothesis_ids == []


# ── InvestigationContextModel ────────────────────────────────────

def test_investigation_context_defaults() -> None:
    ctx = InvestigationContextModel()
    assert ctx.customer_name == ""
    assert ctx.extra == {}


def test_investigation_context_with_values() -> None:
    ctx = InvestigationContextModel(
        customer_name="BlackRock, Inc",
        service_tree_id="49c39e84",
        severity="HIGH",
    )
    assert ctx.customer_name == "BlackRock, Inc"


# ── StreamEventModel ─────────────────────────────────────────────

def test_stream_event_defaults() -> None:
    ev = StreamEventModel(event_type="agent_turn")
    assert ev.agent_name == ""
    assert ev.timestamp  # auto-generated, non-empty


# ── InvestigationModel ───────────────────────────────────────────

def test_investigation_defaults() -> None:
    inv = InvestigationModel()
    assert inv.phase == InvestigationPhase.INITIALIZING
    assert inv.id  # auto-generated
    assert inv.started_at  # auto-generated
    assert inv.symptoms == []
    assert inv.hypotheses == []


def test_investigation_active_hypotheses() -> None:
    inv = InvestigationModel()
    inv.hypotheses.append(HypothesisModel(id="H1", template_id="T", statement="s", category="c", status=HypothesisStatus.ACTIVE))
    inv.hypotheses.append(HypothesisModel(id="H2", template_id="T", statement="s", category="c", status=HypothesisStatus.REFUTED))
    assert len(inv.active_hypotheses()) == 1
    assert inv.active_hypotheses()[0].id == "H1"


def test_investigation_confirmed_hypotheses() -> None:
    inv = InvestigationModel()
    inv.hypotheses.append(HypothesisModel(id="H1", template_id="T", statement="s", category="c", status=HypothesisStatus.CONFIRMED))
    inv.hypotheses.append(HypothesisModel(id="H2", template_id="T", statement="s", category="c", status=HypothesisStatus.ACTIVE))
    assert len(inv.confirmed_hypotheses()) == 1


def test_investigation_collected_er_ids() -> None:
    inv = InvestigationModel()
    inv.evidence.append(EvidenceItemModel(
        id="E1", er_id="ER-001", hypothesis_ids=["H1"],
        agent_name="sli_collector", tool_name="tool",
    ))
    inv.evidence.append(EvidenceItemModel(
        id="E2", er_id="ER-002", hypothesis_ids=["H1"],
        agent_name="incident_collector", tool_name="tool",
    ))
    assert inv.collected_er_ids == {"ER-001", "ER-002"}


def test_investigation_pending_evidence() -> None:
    inv = InvestigationModel()
    inv.evidence_plan.append(EvidenceRequirementModel(
        er_id="ER-001", description="d", technology_tag="kusto", tool_name="t", status="pending",
    ))
    inv.evidence_plan.append(EvidenceRequirementModel(
        er_id="ER-002", description="d", technology_tag="kusto", tool_name="t", status="collected",
    ))
    assert len(inv.pending_evidence()) == 1
    assert inv.pending_evidence()[0].er_id == "ER-001"


def test_investigation_phase_mutation() -> None:
    inv = InvestigationModel()
    inv.phase = InvestigationPhase.TRIAGE
    assert inv.phase == InvestigationPhase.TRIAGE


def test_investigation_backward_compat_aliases() -> None:
    """Verify investigation_state.py re-exports still work."""
    from core.services.investigation.investigation_state import (
        Symptom, Hypothesis, Investigation, EvidenceItem,
        EvidenceRequirement, InvestigationContext, StreamEvent,
    )
    assert Symptom is SymptomModel
    assert Hypothesis is HypothesisModel
    assert Investigation is InvestigationModel
    assert EvidenceItem is EvidenceItemModel
    assert EvidenceRequirement is EvidenceRequirementModel
    assert InvestigationContext is InvestigationContextModel
    assert StreamEvent is StreamEventModel
