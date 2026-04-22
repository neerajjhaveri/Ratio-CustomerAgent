"""Output-parsing middleware for the investigation GroupChat.

Single extraction point: parses raw agent text into ParsedAgentOutput,
then apply_to_investigation mutates the Investigation state.

Every agent emits a ```json block with:
  {"structured_output": {...}, "signals": {"phase_complete", "next_agent", ...}}

If no valid JSON is found, falls back to legacy ---SIGNALS--- parsing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from helper.agent_logger import AgentLogger, get_current_xcv

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)
_SIGNALS_KV_RE = re.compile(r"^([A-Z_]+)\s*:\s*(.+)$")


# ── Parsed result dataclasses ────────────────────────────────────

@dataclass
class ParsedSignals:
    """Routing / lifecycle signals extracted from agent output."""
    phase_complete: str | None = None
    next_agent: str | None = None
    evidence_collected: list[str] = field(default_factory=list)
    investigation_resolved: bool = False
    needs_more_evidence: bool = False
    hypothesis_refuted: bool = False


@dataclass
class ParsedAgentOutput:
    """Fully parsed result of a single agent turn."""

    agent_name: str = ""
    raw_text: str = ""
    is_json_parsed: bool = False
    structured_output: dict[str, Any] = field(default_factory=dict)
    signals: ParsedSignals = field(default_factory=ParsedSignals)

    # Convenience accessors populated from structured_output
    symptoms: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    evaluations: list[dict[str, Any]] = field(default_factory=list)
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    preliminary_verdicts: list[dict[str, Any]] = field(default_factory=list)
    evidence_plan: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)

    display_text: str = ""


# ── Extraction helpers ────────────────────────────────────────────

def _ensure_dict_list(val: Any) -> list[dict]:
    """Coerce val into a list of dicts."""
    if not isinstance(val, list):
        return [val] if isinstance(val, dict) else []
    result = []
    for item in val:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, str):
            result.append({"id": item, "text": item})
    return result


def extract_json_block(text: str) -> dict | None:
    """Extract and parse the last ```json fenced block."""
    matches = _JSON_BLOCK_RE.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1].strip())
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("JSON block found but failed to parse: %s", exc)
        return None


def _strip_json_block(text: str) -> str:
    return _JSON_BLOCK_RE.sub("", text).strip()


def _strip_signals_block(text: str) -> str:
    idx = text.find("---SIGNALS---")
    return text[:idx].strip() if idx >= 0 else text


def _parse_legacy_signals(text: str) -> ParsedSignals:
    """Parse ---SIGNALS--- block into ParsedSignals."""
    signals = ParsedSignals()
    in_block = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "---SIGNALS---":
            in_block = True
            continue
        if in_block and stripped:
            m = _SIGNALS_KV_RE.match(stripped)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if key == "PHASE_COMPLETE":
                    signals.phase_complete = val.lower()
                elif key == "NEXT_AGENT":
                    signals.next_agent = val
                elif key == "EVIDENCE_COLLECTED":
                    signals.evidence_collected = [
                        v.strip() for v in val.strip("[]").split(",") if v.strip()
                    ]
                elif key == "NEEDS_MORE_EVIDENCE":
                    signals.needs_more_evidence = val.lower() in ("true", "yes", "1")
            elif "INVESTIGATION_RESOLVED" in stripped.upper():
                signals.investigation_resolved = True
            elif stripped.startswith("---"):
                break
    return signals


def _parse_json_signals(raw: dict) -> ParsedSignals:
    """Convert the signals dict inside a JSON block to ParsedSignals."""
    signals = ParsedSignals()
    if not isinstance(raw, dict):
        return signals
    if raw.get("phase_complete"):
        signals.phase_complete = str(raw["phase_complete"]).lower()
    if raw.get("next_agent"):
        signals.next_agent = str(raw["next_agent"])
    ec = raw.get("evidence_collected")
    if ec:
        signals.evidence_collected = list(ec) if isinstance(ec, list) else [str(ec)]
    ir = raw.get("investigation_resolved")
    if ir is True or (isinstance(ir, str) and ir.lower() in ("true", "yes", "1")):
        signals.investigation_resolved = True
    nme = raw.get("needs_more_evidence")
    if nme is True or (isinstance(nme, str) and nme.lower() in ("true", "yes", "1")):
        signals.needs_more_evidence = True
    hr = raw.get("hypothesis_refuted")
    if hr is True or (isinstance(hr, str) and hr.lower() in ("true", "yes", "1")):
        signals.hypothesis_refuted = True
    return signals


# ── Main parse function ──────────────────────────────────────────

def parse_agent_output(raw_text: str, agent_name: str = "") -> ParsedAgentOutput:
    """Parse a complete agent turn into ParsedAgentOutput.

    Single entry-point: tries JSON block first, falls back to legacy SIGNALS.
    """
    result = ParsedAgentOutput(agent_name=agent_name, raw_text=raw_text)

    # 1. Try JSON extraction
    json_block = extract_json_block(raw_text)
    if json_block and isinstance(json_block, dict):
        result.is_json_parsed = True
        so_raw = json_block.get("structured_output", {})
        result.structured_output = so_raw if isinstance(so_raw, dict) else {}
        sig_raw = json_block.get("signals", {})
        result.signals = _parse_json_signals(sig_raw if isinstance(sig_raw, dict) else {})
    else:
        result.is_json_parsed = False
        result.signals = _parse_legacy_signals(raw_text)

    # 2. Populate convenience fields from structured_output
    so = result.structured_output
    if so and isinstance(so, dict):
        result.symptoms = _ensure_dict_list(so.get("symptoms", so.get("validated_symptoms", [])))
        result.hypotheses = _ensure_dict_list(so.get("hypotheses", []))
        result.evaluations = _ensure_dict_list(so.get("evaluations", []))
        result.evidence_items = _ensure_dict_list(
            so.get("evidence_items", so.get("evidence_collected", []))
        )
        result.preliminary_verdicts = _ensure_dict_list(so.get("preliminary_verdicts", []))
        result.evidence_plan = _ensure_dict_list(so.get("evidence_plan", []))
        result.actions = _ensure_dict_list(so.get("actions", []))
        report = so.get("report", {})
        result.report = report if isinstance(report, dict) else {}

    # 3. Build display_text
    display = _strip_json_block(raw_text)
    display = _strip_signals_block(display)
    result.display_text = display.strip()

    # ── Log parse result to AgentLogger ────────────────────────────────
    xcv = get_current_xcv()
    if xcv:
        AgentLogger.get_instance().log_output_parsed(
            xcv=xcv,
            agent_name=agent_name,
            is_json_parsed=result.is_json_parsed,
            phase_complete=result.signals.phase_complete or "",
            next_agent=result.signals.next_agent or "",
            investigation_resolved=result.signals.investigation_resolved,
            needs_more_evidence=result.signals.needs_more_evidence,
            hypothesis_refuted=result.signals.hypothesis_refuted,
            symptoms_count=len(result.symptoms),
            hypotheses_count=len(result.hypotheses),
            evaluations_count=len(result.evaluations),
            evidence_items_count=len(result.evidence_items),
            actions_count=len(result.actions),
            raw_output=raw_text,
        )

    return result


# ── Investigation state updater ──────────────────────────────────

def apply_to_investigation(
    parsed: ParsedAgentOutput,
    investigation: "Investigation",
) -> None:
    """Mutate investigation in-place based on parsed agent output.

    Called once per agent turn, immediately after parse_agent_output.
    """
    try:
        _apply_inner(parsed, investigation)
    except Exception as exc:
        logger.exception(
            "Failed to apply parsed output from %s: %s", parsed.agent_name, exc,
        )
        # Surface to App Insights so it's visible in telemetry
        xcv = get_current_xcv()
        if xcv:
            AgentLogger.get_instance().log_investigation_error(
                xcv=xcv,
                investigation_id=investigation.id,
                error=f"apply_to_investigation failed ({parsed.agent_name}): {exc}",
                phase=investigation.phase.value if hasattr(investigation.phase, 'value') else str(investigation.phase),
            )


def _apply_inner(parsed: ParsedAgentOutput, investigation: "Investigation") -> None:
    from .investigation_state import (
        InvestigationPhase,
        Symptom,
        Hypothesis,
        HypothesisStatus,
        EvidenceItem,
        EvidenceVerdict,
        SymptomVerdict,
    )

    sig = parsed.signals

    # ── Phase transition ─────────────────────────────────────
    # phase_complete means "this phase is DONE" → advance to the next phase.
    _PHASE_ORDER = list(InvestigationPhase)
    if sig.phase_complete:
        for i, p in enumerate(_PHASE_ORDER):
            if sig.phase_complete == p.value and i + 1 < len(_PHASE_ORDER):
                next_phase = _PHASE_ORDER[i + 1]
                logger.info(
                    "Phase complete '%s' → advancing to '%s' (agent=%s)",
                    sig.phase_complete, next_phase.value, parsed.agent_name,
                )
                investigation.phase = next_phase
                break

    # Auto-advance to COLLECTING when evidence arrives during PLANNING
    if sig.evidence_collected and investigation.phase == InvestigationPhase.PLANNING:
        investigation.phase = InvestigationPhase.COLLECTING

    if sig.investigation_resolved:
        investigation.phase = InvestigationPhase.COMPLETE

    # ── Symptoms ─────────────────────────────────────────────
    # Triage agent outputs confirmed symptoms with full fields from LLM matching.
    existing_sym_ids = {s.template_id for s in investigation.symptoms}
    for s in parsed.symptoms:
        tid = s.get("template_id", s.get("id", ""))
        if not tid or tid in existing_sym_ids:
            continue
        # Only include confirmed symptoms
        if s.get("status", "confirmed") != "confirmed":
            continue
        cat = s.get("category", "")
        if not cat and "-" in tid:
            cat = tid.split("-")[1].lower()  # SYM-SLI-001 → "sli"
        investigation.symptoms.append(Symptom(
            id=tid,
            template_id=tid,
            text=s.get("text", ""),
            category=cat,
            entities=s.get("enrichments", {}),
            source_signal_type=s.get("source_signal_type", ""),
            weight=int(s.get("weight", 1)),
            severity=s.get("severity", ""),
            signal_strength=float(s.get("signal_strength", 0.0)),
            confirmed=True,
        ))
        existing_sym_ids.add(tid)

    # ── Post-triage hypothesis scoring (programmatic Stage 2) ─
    if sig.phase_complete == "triage" and not investigation.hypotheses:
        _run_post_triage_scoring(investigation)

    # ── Hypotheses ────────────────────────────────────────────
    existing_hyp_ids = {h.id for h in investigation.hypotheses}
    for h in parsed.hypotheses:
        hid = h.get("id", "")
        if hid and hid not in existing_hyp_ids:
            investigation.hypotheses.append(Hypothesis(
                id=hid,
                template_id=hid,
                statement=h.get("statement", ""),
                category=h.get("category", ""),
                confidence=float(h.get("confidence", 0)),
                evidence_needed=h.get("evidence_needed", []),
            ))
            existing_hyp_ids.add(hid)

    # ── Hypothesis evaluations (from reasoner) ────────────────
    hyp_map = {h.id: h for h in investigation.hypotheses}
    for ev in parsed.evaluations:
        hid = ev.get("hypothesis_id", "")
        if hid in hyp_map:
            hyp = hyp_map[hid]
            old_status = hyp.status.value if hasattr(hyp.status, 'value') else str(hyp.status)
            hyp.confidence = float(ev.get("confidence", hyp.confidence))
            status_str = (ev.get("status", "")).upper()
            if status_str == "CONFIRMED":
                hyp.status = HypothesisStatus.CONFIRMED
            elif status_str == "REFUTED":
                hyp.status = HypothesisStatus.REFUTED
            elif status_str == "CONTRIBUTING":
                hyp.status = HypothesisStatus.CONTRIBUTING
            new_status = hyp.status.value if hasattr(hyp.status, 'value') else str(hyp.status)
            # Log hypothesis transition
            if old_status != new_status:
                xcv = get_current_xcv()
                if xcv:
                    AgentLogger.get_instance().log_hypothesis_transition(
                        xcv=xcv,
                        investigation_id=investigation.id,
                        hypothesis_id=hid,
                        old_status=old_status,
                        new_status=new_status,
                        confidence=hyp.confidence,
                    )
            for eev in ev.get("evidence", []):
                eid = eev.get("evidence_id", "")
                verdict_str = eev.get("verdict", "")
                if eid and verdict_str:
                    try:
                        hyp.verdicts[eid] = EvidenceVerdict(verdict_str.lower())
                    except ValueError:
                        pass

            # ── Symptom verdicts (per-symptom verification from reasoner) ─
            for sv in ev.get("symptom_verdicts", []):
                sid = sv.get("symptom_id", "")
                verdict_str = sv.get("verdict", "")
                if sid and verdict_str:
                    try:
                        hyp.symptom_verdicts[sid] = SymptomVerdict(verdict_str.lower())
                    except ValueError:
                        pass

    # ── Evidence items ────────────────────────────────────────
    existing_ev_ids = {e.id for e in investigation.evidence}
    for ei in parsed.evidence_items:
        eid = ei.get("id", ei.get("er_id", ""))
        if eid and eid not in existing_ev_ids:
            investigation.evidence.append(EvidenceItem(
                id=eid,
                er_id=ei.get("er_id", eid),
                hypothesis_ids=ei.get("hypothesis_ids", []),
                agent_name=ei.get("agent_name", parsed.agent_name),
                tool_name=ei.get("tool_name", ""),
                summary=ei.get("summary", ""),
                preliminary_verdict=ei.get("preliminary_verdict", ""),
            ))
            existing_ev_ids.add(eid)

    # ── Preliminary verdicts ──────────────────────────────────
    for pv in parsed.preliminary_verdicts:
        hid = pv.get("hypothesis_id", "")
        if hid in hyp_map:
            verdict_str = pv.get("verdict", "")
            if verdict_str:
                try:
                    hyp_map[hid].verdicts[f"prelim_{parsed.agent_name}"] = \
                        EvidenceVerdict(verdict_str.lower())
                except ValueError:
                    pass

    # ── Actions ───────────────────────────────────────────────
    for act in parsed.actions:
        action_entry = {
            "action_id": act.get("action_id", act.get("id", "")),
            "display_name": act.get("display_name", ""),
            "tier": act.get("tier", ""),
            "priority": act.get("priority", 0),
            "justification": act.get("justification", ""),
            "target_hypotheses": act.get("target_hypotheses", []),
        }
        if action_entry["action_id"]:
            investigation.actions.append(action_entry)

    # ── Recompute evidence_delta for all hypotheses ───────────
    collected = investigation.collected_er_ids
    for hyp in investigation.hypotheses:
        hyp.evidence_delta = [er for er in hyp.evidence_needed if er not in collected]


def _run_post_triage_scoring(investigation: "Investigation") -> None:
    """Run programmatic hypothesis scoring after the triage agent completes.

    Stage 2 of the hybrid pipeline: scores hypotheses by measuring overlap
    between confirmed symptoms (from LLM triage) and each hypothesis's
    expected_symptoms, weighted by signal strength.

    Scoring config is read from investigation.context.extra["scoring_config"],
    which was stored by the investigation_runner at creation time.
    """
    from .hypothesis_scorer import score_hypotheses

    confirmed = [s for s in investigation.symptoms if s.confirmed]
    if not confirmed:
        logger.warning("Post-triage scoring: no confirmed symptoms (total=%d), skipping",
                       len(investigation.symptoms))
        return

    logger.info(
        "Post-triage scoring: %d confirmed symptoms, running hypothesis scorer",
        len(confirmed),
    )
    scoring_config = investigation.context.extra.get("scoring_config")
    ranked = score_hypotheses(confirmed, scoring_config=scoring_config)
    investigation.hypotheses = ranked

    # Log scoring results
    xcv = get_current_xcv()
    if xcv:
        scores_str = "; ".join(f"{h.id}={h.match_score:.4f}" for h in ranked[:5])
        AgentLogger.get_instance().log_hypothesis_scoring(
            xcv=xcv,
            input_symptom_count=len(confirmed),
            output_hypothesis_count=len(ranked),
            top_hypothesis_id=ranked[0].id if ranked else "",
            top_score=ranked[0].match_score if ranked else 0.0,
            all_scores=scores_str,
        )

    if ranked:
        logger.info(
            "Post-triage scoring complete: %d hypotheses, top=%s (score=%.4f)",
            len(ranked), ranked[0].id, ranked[0].match_score,
        )
        # Emit per-hypothesis selection events so the UI shows each candidate
        for rank_idx, hyp in enumerate(ranked, start=1):
            AgentLogger.get_instance().log_hypothesis_selected(
                xcv=xcv,
                investigation_id=investigation.id,
                hypothesis_id=hyp.id,
                statement=hyp.statement,
                match_score=hyp.match_score,
                matched_symptoms=", ".join(hyp.matched_symptoms),
                evidence_needed=", ".join(hyp.evidence_needed),
                rank=rank_idx,
                total_hypotheses=len(ranked),
            )
    else:
        logger.warning("Post-triage scoring: no hypotheses met threshold")
