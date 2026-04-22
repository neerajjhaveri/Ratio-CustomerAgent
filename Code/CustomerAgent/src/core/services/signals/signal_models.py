"""Data models for the SignalBuilder pipeline.

Defines the output structures produced by signal evaluation:
- ActivatedSignal: one granularity that passed activation_rules
- TypeSignalResult: aggregated result for one signal type
- CompoundSignalResult: fusion result across multiple types
- SignalBuilderResult: top-level output of a single poll cycle
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ── Activated granularity ─────────────────────────────────────────

@dataclass
class ActivatedSignal:
    """A single granularity that passed its activation_rules."""

    signal_type_id: str
    signal_name: str
    granularity: str
    confidence: str
    strength: float
    raw_strength: float = 0.0
    activation_summary: str = ""
    matched_rows: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type_id": self.signal_type_id,
            "signal_name": self.signal_name,
            "granularity": self.granularity,
            "confidence": self.confidence,
            "strength": round(self.strength, 1),
            "raw_strength": round(self.raw_strength, 4),
            "activation_summary": self.activation_summary,
            "matched_row_count": len(self.matched_rows),
            "timestamp": self.timestamp.isoformat(),
        }

    def to_model(self):
        from core.models.signals.activated_signal import ActivatedSignalModel
        return ActivatedSignalModel(
            signal_type_id=self.signal_type_id,
            signal_name=self.signal_name,
            granularity=self.granularity,
            confidence=self.confidence,
            strength=self.strength,
            raw_strength=self.raw_strength,
            activation_summary=self.activation_summary,
            matched_row_count=len(self.matched_rows),
            timestamp=self.timestamp,
        )


# ── Per-type aggregate ────────────────────────────────────────────

@dataclass
class TypeSignalResult:
    """Aggregated result for one signal type after evaluating all granularities."""

    signal_type_id: str
    signal_name: str
    has_data: bool
    row_count: int
    activated_signals: list[ActivatedSignal]
    max_strength: float = 0.0
    raw_max_strength: float = 0.0
    best_confidence: str = "Low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type_id": self.signal_type_id,
            "signal_name": self.signal_name,
            "has_data": self.has_data,
            "row_count": self.row_count,
            "max_strength": round(self.max_strength, 1),
            "raw_max_strength": round(self.raw_max_strength, 4),
            "best_confidence": self.best_confidence,
            "activated_granularities": [s.to_dict() for s in self.activated_signals],
        }


# ── Compound signal ───────────────────────────────────────────────

@dataclass
class CompoundSignalResult:
    """Result of evaluating a compound signal rule."""

    compound_id: str
    compound_name: str
    activated: bool
    confidence: str
    strength: float
    raw_strength: float = 0.0
    contributing_types: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "compound_id": self.compound_id,
            "compound_name": self.compound_name,
            "activated": self.activated,
            "confidence": self.confidence,
            "strength": round(self.strength, 1),
            "raw_strength": round(self.raw_strength, 4),
            "contributing_types": self.contributing_types,
            "rationale": self.rationale,
        }


# ── Top-level poll result ────────────────────────────────────────

@dataclass
class SignalBuilderResult:
    """Output of a single SignalBuilder poll cycle for one customer × service_tree_id."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    type_results: list[TypeSignalResult] = field(default_factory=list)
    compound_results: list[CompoundSignalResult] = field(default_factory=list)
    action: str = "quiet"  # "invoke_group_chat" | "watchlist" | "quiet"
    customer_name: str = ""
    service_tree_id: str = ""
    service_name: str = ""
    xcv: str = ""

    @property
    def all_activated_signals(self) -> list[ActivatedSignal]:
        """Flat list of all activated individual signals."""
        return [s for tr in self.type_results for s in tr.activated_signals]

    @property
    def activated_compounds(self) -> list[CompoundSignalResult]:
        return [c for c in self.compound_results if c.activated]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "customer_name": self.customer_name,
            "service_tree_id": self.service_tree_id,
            "service_name": self.service_name,
            "type_results": [t.to_dict() for t in self.type_results],
            "compound_results": [c.to_dict() for c in self.compound_results],
        }


# ── Strength formula evaluator ───────────────────────────────────

# Allowed names that can appear in strength formulas (safe math subset)
_SAFE_BUILTINS = {"log2": math.log2, "log": math.log, "sqrt": math.sqrt, "abs": abs, "min": min, "max": max}

# Pattern to detect unsafe constructs
_UNSAFE_PATTERN = re.compile(r"(__|\bimport\b|\bexec\b|\beval\b|\bopen\b|\bos\b|\bsys\b)")


def evaluate_strength(formula: str, variables: dict[str, Any]) -> float:
    """Safely evaluate a strength_formula string.

    Supports basic arithmetic (+, -, *, /), ternary-style expressions
    rewritten to Python, log2(), and variable references.

    Args:
        formula: The formula string from signal_template.json.
        variables: Name→value bindings (snake_case field names).

    Returns:
        Computed strength as a float.
    """
    if _UNSAFE_PATTERN.search(formula):
        raise ValueError(f"Unsafe construct in formula: {formula}")

    # Rewrite ternary: (cond ? a : b) → (a if cond else b)
    py_expr = _rewrite_ternaries(formula)
    # Rewrite boolean literals
    py_expr = py_expr.replace("true", "True").replace("false", "False")

    namespace = {**_SAFE_BUILTINS, **variables}
    try:
        result = eval(py_expr, {"__builtins__": {}}, namespace)  # noqa: S307
        return float(result)
    except Exception as exc:
        raise ValueError(f"Failed to evaluate '{formula}': {exc}") from exc


def _rewrite_ternaries(expr: str) -> str:
    """Rewrite C-style ternary (cond ? a : b) to Python (a if cond else b).

    Handles nested ternaries by processing innermost first.
    """
    # Match innermost ternary: no nested ? inside
    pattern = re.compile(r"\(([^?()]+)\?([^?():]+):([^?()]+)\)")
    prev = None
    while prev != expr:
        prev = expr
        expr = pattern.sub(r"(\2 if \1 else \3)", expr)
    return expr


# ---------------------------------------------------------------------------
# Scoring normalisation helpers
# ---------------------------------------------------------------------------

_SCORE_LABELS = {
    0: "None",
    1: "Low",
    2: "Moderate",
    3: "Significant",
    4: "High",
    5: "Critical",
}


def normalize_strength(
    raw: float,
    max_raw: float,
    *,
    scale_max: float = 5.0,
    floor: float = 0.5,
) -> float:
    """Normalise a raw strength value to the 0-*scale_max* range.

    * Clamps the ratio at 1.0 so the result never exceeds *scale_max*.
    * If *raw* > 0 the minimum returned value is *floor* so that any
      activated signal always registers on the scale.
    """
    if raw <= 0 or max_raw <= 0:
        return 0.0
    normalised = min(raw / max_raw, 1.0) * scale_max
    return max(normalised, floor)


def strength_label(value: float) -> str:
    """Return a human-readable label for a normalised 0-5 strength value."""
    bucket = max(0, min(5, round(value)))
    return _SCORE_LABELS.get(bucket, "Unknown")
