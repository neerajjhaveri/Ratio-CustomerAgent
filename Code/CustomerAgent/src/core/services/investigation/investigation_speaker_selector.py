"""Speaker selector for the investigation GroupChat.

Three-stage model routing:
  Stage 1 & 2 are pre-computed (symptom matching + hypothesis scoring).
  Stage 3 is the GroupChat:
    triage (validate) → evidence for top hypothesis → reasoning →
      if confirmed: acting → notifying → complete
      if refuted: orchestrator picks next hypothesis → evidence (reuse + delta)

Cycle support:
  - needs_more_evidence: backtrack to evidence_planner (max 2 per hypothesis)
  - hypothesis_refuted: advance to next ranked hypothesis via orchestrator

Compatible with GroupChatBuilder's selection_func API:
  selection_func(GroupChatState) → str (next participant name)
"""

from __future__ import annotations

import logging
from typing import Any

from .investigation_output_parser import ParsedAgentOutput, parse_agent_output
from helper.agent_logger import AgentLogger, get_current_xcv

logger = logging.getLogger(__name__)

_MAX_EVIDENCE_CYCLES = 2

# Phase transition table: completed phase → next agent name
_PHASE_TRANSITIONS: dict[str, str] = {
    "triage": "investigation_orchestrator",      # orchestrator reviews pre-scored hypotheses
    "hypothesizing": "evidence_planner",          # plan evidence for selected hypothesis
    "planning": "investigation_orchestrator",     # orchestrator dispatches collectors
    "collecting": "reasoner",
    "reasoning": "action_planner",                # default; overridden by cycle/refute logic
    "acting": "notification_agent",
    "notifying": "investigation_orchestrator",
}


def _get_last_message_text(state: Any) -> str:
    """Get the text of the last message in conversation."""
    conversation = state.conversation
    if not conversation:
        return ""
    last = conversation[-1]
    if hasattr(last, "text") and last.text:
        return last.text
    if hasattr(last, "content"):
        contents = last.content if isinstance(last.content, list) else [last.content]
        parts = []
        for c in contents:
            if hasattr(c, "text"):
                parts.append(c.text)
            elif isinstance(c, str):
                parts.append(c)
        return " ".join(parts)
    return str(last)


def _get_last_speaker(state: Any) -> str | None:
    """Get the author/name of the last message."""
    conversation = state.conversation
    if not conversation:
        return None
    last = conversation[-1]
    return getattr(last, "author_name", None) or getattr(last, "name", None)


def create_investigation_speaker_selector(
    participant_names: list[str],
    orchestrator_name: str = "investigation_orchestrator",
):
    """Create the speaker selection function for the investigation GroupChat.

    Args:
        participant_names: List of valid participant names from config.
        orchestrator_name: Name of the orchestrator agent.

    Returns:
        A function: GroupChatState → str (next participant name).
    """
    valid_names = set(participant_names)
    evidence_cycle_count = 0
    hypothesis_cycle_count = 0  # track how many hypotheses we've evaluated

    def _resolve(candidate: str) -> str | None:
        """Resolve a candidate name, return it if valid."""
        if candidate in valid_names:
            return candidate
        return None

    def _log_selection(last: str, next_: str, reason: str) -> None:
        xcv = get_current_xcv()
        if xcv:
            AgentLogger.get_instance().log_speaker_selected(
                xcv=xcv,
                last_speaker=last,
                next_speaker=next_,
                reason=reason,
                evidence_cycle=evidence_cycle_count,
                hypothesis_cycle=hypothesis_cycle_count,
            )

    def select_next_speaker(state: Any) -> str:
        nonlocal evidence_cycle_count, hypothesis_cycle_count

        conversation = state.conversation
        participant_keys = list(state.participants.keys())
        default = orchestrator_name if orchestrator_name in participant_keys else participant_keys[0]

        # Safety limit
        if state.current_round >= 40:
            logger.warning("Max rounds (%d) reached, returning orchestrator.", state.current_round)
            return default

        # First turn → orchestrator
        if not conversation or len(conversation) <= 1:
            return default

        last_text = _get_last_message_text(state)
        last_speaker = _get_last_speaker(state)

        # Parse via output_parser — single extraction point
        parsed = parse_agent_output(last_text, agent_name=last_speaker or "")
        sig = parsed.signals

        # Priority 1: Investigation resolved → orchestrator to wrap up
        if sig.investigation_resolved:
            _log_selection(last_speaker or "", default, "investigation_resolved")
            return default

        # Priority 2: Explicit next_agent signal
        if sig.next_agent:
            resolved = _resolve(sig.next_agent)
            if resolved:
                _log_selection(last_speaker or "", resolved, f"explicit_next_agent={sig.next_agent}")
                return resolved

        # Priority 3: Phase transition (with cycle + hypothesis-refute support)
        if sig.phase_complete:
            # Cycle support: reasoning + needs_more_evidence → back to evidence_planner
            if sig.phase_complete == "reasoning" and sig.needs_more_evidence:
                if evidence_cycle_count < _MAX_EVIDENCE_CYCLES:
                    evidence_cycle_count += 1
                    target = _resolve("evidence_planner")
                    if target:
                        logger.info(
                            "Evidence cycle %d/%d: reasoning → evidence_planner",
                            evidence_cycle_count, _MAX_EVIDENCE_CYCLES,
                        )
                        _log_selection(last_speaker or "", target, f"evidence_cycle={evidence_cycle_count}")
                        return target
                else:
                    logger.info(
                        "Max evidence cycles (%d) reached, proceeding to action_planner.",
                        _MAX_EVIDENCE_CYCLES,
                    )

            # Hypothesis refuted → orchestrator picks next hypothesis
            if sig.phase_complete == "reasoning" and getattr(sig, "hypothesis_refuted", False):
                hypothesis_cycle_count += 1
                evidence_cycle_count = 0  # reset evidence cycles for new hypothesis
                logger.info(
                    "Hypothesis #%d refuted, routing to orchestrator for next hypothesis",
                    hypothesis_cycle_count,
                )
                _log_selection(last_speaker or "", default, f"hypothesis_refuted_cycle={hypothesis_cycle_count}")
                return default

            next_agent = _PHASE_TRANSITIONS.get(sig.phase_complete)
            if next_agent:
                resolved = _resolve(next_agent)
                if resolved:
                    logger.info("Phase transition: %s → %s", sig.phase_complete, resolved)
                    _log_selection(last_speaker or "", resolved, f"phase_transition={sig.phase_complete}")
                    return resolved

        # Priority 4: Evidence collected → orchestrator decides
        if sig.evidence_collected:
            return default

        # Priority 5: After specialist → orchestrator
        if last_speaker and last_speaker != default:
            return default

        # Priority 6: Keyword fallback from orchestrator
        if last_speaker == default:
            result = _keyword_routing(last_text, parsed, valid_names)
            if result:
                return result

        return default

    return select_next_speaker


def _keyword_routing(
    text: str,
    parsed: ParsedAgentOutput,
    valid_names: set[str],
) -> str | None:
    """Keyword-based routing fallback when structured signals are absent."""
    text_lower = text.lower()

    for agent_name, keywords in [
        ("triage_agent", ["triage", "classify", "signal"]),
        ("hypothesis_selector", ["hypothes", "hypothesis"]),
        ("evidence_planner", ["plan", "evidence plan"]),
        ("reasoner", ["reason", "evaluate", "analyze evidence", "confidence"]),
        ("action_planner", ["action", "recommend", "mitigat"]),
        ("notification_agent", ["notify", "notification", "alert stakeholder"]),
    ]:
        if any(kw in text_lower for kw in keywords):
            if agent_name in valid_names:
                return agent_name

    return None
