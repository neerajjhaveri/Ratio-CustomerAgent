"""Stage 2 — Hypothesis Scorer.

Scores hypotheses by measuring overlap between confirmed symptoms and each
hypothesis's expected_symptoms, weighted by signal strength.  This is purely
programmatic — no LLM is involved.

Hybrid model flow:
  [Triage Agent / LLM] → Confirmed Symptoms
                       → [HypothesisScorer / programmatic] → Ranked Hypotheses → Evidence

Scoring parameters are read from the investigation_workflow.scoring config
in agents_config.json.  Supported options:
  strength_aggregation: avg | max | min  (default: avg)
  default_weight:       fallback weight for symptoms not in template (default: 1)
  min_score_threshold:  discard hypotheses below this score (default: 0.0)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from .investigation_state import Hypothesis, HypothesisStatus, Symptom
from helper.agent_logger import AgentLogger, get_current_xcv

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config"))
_HYPOTHESES_DIR = os.path.join(_CONFIG_DIR, "hypotheses")


# ── Config loading ────────────────────────────────────────────────

def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_hypothesis_templates() -> list[dict[str, Any]]:
    """Load all hypothesis templates from config/hypotheses/*.json."""
    templates: list[dict[str, Any]] = []
    if not os.path.isdir(_HYPOTHESES_DIR):
        logger.warning("Hypotheses config directory not found: %s", _HYPOTHESES_DIR)
        return templates
    for filename in os.listdir(_HYPOTHESES_DIR):
        if not filename.endswith(".json"):
            continue
        data = _load_json(os.path.join(_HYPOTHESES_DIR, filename))
        for h in data.get("hypotheses", []):
            # Skip pending hypotheses (e.g., risk hypotheses awaiting signal types)
            if h.get("status") == "pending":
                logger.debug("Skipping pending hypothesis: %s", h["id"])
                continue
            h["_source_file"] = filename
            templates.append(h)
    return templates


# ── Scoring ───────────────────────────────────────────────────────

def _compute_match_score(
    expected: list[str],
    confirmed_ids: set[str],
    symptom_lookup: dict[str, Symptom],
    scoring_config: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Compute signal-proportional match score.

    Formula:
        match_score = (weighted_matched / weighted_total) × agg_signal_strength

    Where:
        weighted_matched = sum(weight for each expected symptom that is confirmed)
        weighted_total   = sum(weight for all expected symptoms, using default_weight
                           for symptoms not in lookup)
        agg_signal_strength = aggregated signal_strength of matched symptoms
                              (avg, max, or min per scoring_config)

    Returns (score, list_of_matched_template_ids).
    """
    if not expected:
        return 0.0, []

    cfg = scoring_config or {}
    default_weight = cfg.get("default_weight", 1)
    strength_agg = cfg.get("strength_aggregation", "avg")

    matched_ids: list[str] = []
    weighted_matched = 0.0
    weighted_total = 0.0
    strengths: list[float] = []

    for sym_id in expected:
        sym = symptom_lookup.get(sym_id)
        weight = sym.weight if sym else default_weight
        weighted_total += weight

        if sym_id in confirmed_ids:
            matched_ids.append(sym_id)
            weighted_matched += weight
            if sym:
                strengths.append(sym.signal_strength)

    if weighted_total == 0:
        return 0.0, matched_ids

    overlap_ratio = weighted_matched / weighted_total

    if strengths:
        if strength_agg == "max":
            agg_strength = max(strengths)
        elif strength_agg == "min":
            agg_strength = min(strengths)
        else:  # avg (default)
            agg_strength = sum(strengths) / len(strengths)
    else:
        agg_strength = 0.0

    score = overlap_ratio * agg_strength
    return round(score, 4), matched_ids


# ── Main scorer entry point ──────────────────────────────────────

def score_hypotheses(
    confirmed_symptoms: list[Symptom],
    scoring_config: dict[str, Any] | None = None,
) -> list[Hypothesis]:
    """Stage 2: Score and rank hypotheses by symptom overlap × signal strength.

    For each hypothesis template:
    1. Count which expected_symptoms are confirmed
    2. If matched >= min_symptoms_for_match, compute match_score
    3. Create ranked Hypothesis instances

    Args:
        confirmed_symptoms: Symptoms confirmed by the triage agent.
        scoring_config: Optional scoring parameters from investigation_workflow.scoring.
            Keys: strength_aggregation (avg|max|min), default_weight (int),
                  min_score_threshold (float).

    Returns hypotheses sorted by match_score descending.
    Only hypotheses meeting min_symptoms_for_match are included.
    """
    templates = load_hypothesis_templates()
    cfg = scoring_config or {}
    min_score = cfg.get("min_score_threshold", 0.0)

    # Build lookup: template_id → Symptom
    confirmed_ids: set[str] = set()
    symptom_lookup: dict[str, Symptom] = {}
    for sym in confirmed_symptoms:
        confirmed_ids.add(sym.template_id)
        symptom_lookup[sym.template_id] = sym

    candidates: list[Hypothesis] = []

    for tmpl in templates:
        hyp_id = tmpl["id"]
        expected = tmpl.get("expected_symptoms", [])
        min_match = tmpl.get("min_symptoms_for_match", 2)

        score, matched_ids = _compute_match_score(
            expected, confirmed_ids, symptom_lookup, scoring_config=cfg,
        )
        matched_count = len(matched_ids)

        if matched_count < min_match:
            logger.debug(
                "Hypothesis %s: matched %d/%d (need %d), skipping",
                hyp_id, matched_count, len(expected), min_match,
            )
            continue

        if score < min_score:
            logger.debug(
                "Hypothesis %s: score=%.4f below threshold %.4f, skipping",
                hyp_id, score, min_score,
            )
            continue

        hypothesis = Hypothesis(
            id=hyp_id,
            template_id=hyp_id,
            statement=tmpl.get("statement", ""),
            category=tmpl.get("category", ""),
            status=HypothesisStatus.ACTIVE,
            expected_symptoms=expected,
            matched_symptoms=matched_ids,
            match_score=score,
            min_symptoms_for_match=min_match,
            evidence_needed=tmpl.get("evidence_needed", []),
        )
        candidates.append(hypothesis)
        logger.info(
            "Hypothesis %s (%s): score=%.4f matched=%d/%d",
            hyp_id, tmpl["name"], score, matched_count, len(expected),
        )

    # Sort by match_score descending — highest signal affinity first
    candidates.sort(key=lambda h: h.match_score, reverse=True)

    # Log scoring results
    xcv = get_current_xcv()
    if xcv:
        scores_str = "; ".join(f"{h.id}={h.match_score:.4f}" for h in candidates[:5])
        AgentLogger.get_instance().log_hypothesis_scoring(
            xcv=xcv,
            input_symptom_count=len(confirmed_symptoms),
            output_hypothesis_count=len(candidates),
            top_hypothesis_id=candidates[0].id if candidates else "",
            top_score=candidates[0].match_score if candidates else 0.0,
            all_scores=scores_str,
        )

    return candidates
