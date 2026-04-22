"""Tests for signal pipeline Pydantic models."""
from __future__ import annotations

from datetime import datetime, timezone

from core.models.signals.activated_signal import ActivatedSignalModel
from core.models.signals.type_signal_result import TypeSignalResultModel
from core.models.signals.compound_signal_result import CompoundSignalResultModel
from core.models.signals.signal_builder_result import SignalBuilderResultModel


# ── ActivatedSignalModel ─────────────────────────────────────────

def test_activated_signal_required_fields() -> None:
    ts = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    s = ActivatedSignalModel(
        signal_type_id="SIG-TYPE-1",
        signal_name="SLI Breach",
        granularity="subscription_region",
        confidence="Medium",
        strength=2.5,
        timestamp=ts,
    )
    assert s.signal_type_id == "SIG-TYPE-1"
    assert s.raw_strength == 0.0
    assert s.matched_row_count == 0


def test_activated_signal_all_fields() -> None:
    ts = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    s = ActivatedSignalModel(
        signal_type_id="SIG-TYPE-2",
        signal_name="Support Surge",
        granularity="single_case",
        confidence="High",
        strength=3.8,
        raw_strength=11.4,
        activation_summary="42 SRs in 5m",
        matched_row_count=42,
        timestamp=ts,
    )
    assert s.raw_strength == 11.4
    assert s.matched_row_count == 42


# ── TypeSignalResultModel ────────────────────────────────────────

def test_type_signal_result_defaults() -> None:
    r = TypeSignalResultModel(
        signal_type_id="SIG-TYPE-1",
        signal_name="SLI Breach",
        has_data=True,
        row_count=5,
    )
    assert r.max_strength == 0.0
    assert r.best_confidence == "Low"
    assert r.activated_granularities == []


def test_type_signal_result_with_signals() -> None:
    ts = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    sig = ActivatedSignalModel(
        signal_type_id="SIG-TYPE-1", signal_name="SLI",
        granularity="cross_region", confidence="High",
        strength=4.0, timestamp=ts,
    )
    r = TypeSignalResultModel(
        signal_type_id="SIG-TYPE-1", signal_name="SLI",
        has_data=True, row_count=10, max_strength=4.0,
        best_confidence="High", activated_granularities=[sig],
    )
    assert len(r.activated_granularities) == 1
    assert r.activated_granularities[0].granularity == "cross_region"


# ── CompoundSignalResultModel ────────────────────────────────────

def test_compound_signal_defaults() -> None:
    c = CompoundSignalResultModel(
        compound_id="COMP-001",
        compound_name="SLI + Outage",
        activated=True,
        confidence="High",
        strength=4.7,
    )
    assert c.contributing_types == []
    assert c.rationale == ""


# ── SignalBuilderResultModel ─────────────────────────────────────

def test_signal_builder_result_defaults() -> None:
    ts = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    r = SignalBuilderResultModel(timestamp=ts)
    assert r.action == "quiet"
    assert r.customer_name == ""
    assert r.type_results == []
    assert r.compound_results == []


def test_signal_builder_result_serialization() -> None:
    ts = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    r = SignalBuilderResultModel(
        timestamp=ts, action="invoke_group_chat",
        customer_name="BlackRock, Inc",
        service_tree_id="49c39e84",
    )
    data = r.model_dump()
    assert data["action"] == "invoke_group_chat"
    assert data["customer_name"] == "BlackRock, Inc"
