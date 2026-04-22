"""Investigation runner — wires SignalBuilderResult → Investigation GroupChat.

Hybrid model:
  Stage 1 (LLM — triage agent): Matches raw signals against symptom templates
  Stage 2 (programmatic):       HypothesisScorer ranks hypotheses after triage
  Stage 3 (GroupChat):          Sequential hypothesis evaluation with evidence
                                collection and reasoning

Scoring config is stored in investigation.context.extra["scoring_config"]
so the output_parser can pass it to the hypothesis_scorer after triage.

This is the `on_group_chat` callback for signal_builder.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from agent_framework import Agent, AgentResponse, AgentResponseUpdate, Message, WorkflowEvent
from agent_framework.orchestrations import GroupChatBuilder

from ...agent_factory import load_config, create_agents
from .investigation_state import Investigation, InvestigationContext, InvestigationPhase, HypothesisStatus
from .investigation_output_parser import parse_agent_output, apply_to_investigation, extract_json_block
from ..signals.signal_models import SignalBuilderResult
from ..signals.symptom_matcher import load_symptom_templates, format_templates_for_prompt
from .hypothesis_scorer import score_hypotheses
from helper.agent_logger import AgentLogger, get_current_xcv, set_current_xcv, set_current_tool_stage, generate_xcv

logger = logging.getLogger(__name__)


def _build_task_message(investigation: Investigation) -> str:
    """Build the initial investigation task message with raw signals and symptom templates.

    The triage agent (LLM) uses the symptom templates as reference material to
    match raw signals to confirmed symptoms.  Hypothesis scoring happens
    programmatically AFTER triage completes.
    """
    result = investigation.signal_builder_result

    # -- Activated signals --
    signals_summary = []
    for sig in result.all_activated_signals:
        signals_summary.append(
            f"- [{sig.signal_type_id}] {sig.signal_name} "
            f"(granularity={sig.granularity}, confidence={sig.confidence}, "
            f"strength={sig.strength:.3f}): {sig.activation_summary}"
        )

    compounds_summary = []
    for comp in result.activated_compounds:
        compounds_summary.append(
            f"- [{comp.compound_id}] {comp.compound_name} "
            f"(confidence={comp.confidence}, strength={comp.strength:.3f}): {comp.rationale}"
        )

    # -- Signal data rows (for triage agent to evaluate filters) --
    signal_data_lines = []
    for tr in result.type_results:
        if not tr.activated_signals:
            continue
        signal_data_lines.append(f"  Signal Type: {tr.signal_type_id} (strength={tr.max_strength:.3f})")
        for sig in tr.activated_signals:
            if sig.matched_rows:
                signal_data_lines.append(f"    {sig.signal_name}: {len(sig.matched_rows)} matched rows")
                for i, row in enumerate(sig.matched_rows[:5]):  # limit to 5 rows per signal
                    signal_data_lines.append(f"      row[{i}]: {json.dumps(row, default=str)}")
                if len(sig.matched_rows) > 5:
                    signal_data_lines.append(f"      ... ({len(sig.matched_rows) - 5} more rows)")
        signal_data_lines.append("")

    # -- Symptom templates (reference material for triage agent) --
    templates = load_symptom_templates()
    template_ref = format_templates_for_prompt(templates)

    parts = [
        f"INVESTIGATION TRIGGERED for customer '{result.customer_name}' "
        f"(service_tree_id: {result.service_tree_id})",
        f"Decision: {result.action}",
        f"Timestamp: {result.timestamp.isoformat()}",
        "",
        "== Activated Signals ==",
    ]
    parts.extend(signals_summary if signals_summary else ["(none)"])
    parts.append("")
    parts.append("== Activated Compound Signals ==")
    parts.extend(compounds_summary if compounds_summary else ["(none)"])
    parts.append("")
    parts.append("== Signal Data Rows ==")
    parts.extend(signal_data_lines if signal_data_lines else ["(no data rows)"])
    parts.append("")
    parts.append("== Symptom Templates (Reference Material) ==")
    parts.append("Match these templates against the signal data above.")
    parts.append("A symptom is CONFIRMED when its criteria are met by the data.")
    parts.append("")
    parts.append(template_ref)
    parts.append("")
    parts.append(
        "TRIAGE AGENT: Evaluate the signal data against the symptom templates above. "
        "For each template whose criteria are met, confirm the symptom in your output. "
        "Compute any llm_derived fields by reasoning over the data rows. "
        "Evaluate cross-source correlations (e.g., time overlap for SYM-OUT-003). "
        "Then assign the investigation category and severity."
    )
    return "\n".join(parts)


def _create_investigation(
    result: SignalBuilderResult,
    scoring_config: dict[str, Any] | None = None,
) -> Investigation:
    """Create an Investigation instance — no pre-computed stages.

    Hybrid model:
      Stage 1 (LLM):          Triage agent matches signals → symptoms during GroupChat
      Stage 2 (programmatic): HypothesisScorer runs AFTER triage completes
                              (wired through output_parser)

    The scoring_config is stored in investigation.context.extra so the
    output_parser can pass it to hypothesis_scorer after triage.
    """
    investigation = Investigation(
        phase=InvestigationPhase.INITIALIZING,
        context=InvestigationContext(
            customer_name=result.customer_name,
            service_tree_id=result.service_tree_id,
        ),
        signal_builder_result=result,
    )

    # Store scoring config for post-triage hypothesis scoring
    if scoring_config:
        investigation.context.extra["scoring_config"] = scoring_config

    logger.info(
        "Investigation created (%d activated signals, %d compounds). "
        "Triage agent will perform symptom matching.",
        len(result.all_activated_signals),
        len(result.activated_compounds),
    )

    return investigation


async def run_investigation(
    result: SignalBuilderResult,
    config: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the investigation GroupChat for a SignalBuilderResult.

    This is the main entry point — pass as on_group_chat callback to
    run_signal_builder_loop, or call directly for testing.

    Yields structured events compatible with the existing orchestrator streaming format.
    """
    if config is None:
        config = load_config()

    inv_workflow_cfg = config.get("investigation_workflow")
    if not inv_workflow_cfg:
        logger.error("No 'investigation_workflow' section in agents_config.json")
        return

    # Create investigation state
    scoring_config = inv_workflow_cfg.get("scoring")
    investigation = _create_investigation(result, scoring_config=scoring_config)

    # Create agents (reuses agent_factory — creates all agents, we filter)
    all_agents_dict, capture_mw, eval_mw, injection_mw, llm_log_mw, prompts = await create_agents(config)

    async def _close_all_agents() -> None:
        """Close MCP connections on all agents to avoid cross-task cancel scope errors."""
        for agent in all_agents_dict.values():
            mcp_tools = getattr(agent, "mcp_tools", [])
            for mcp_tool in mcp_tools:
                try:
                    if getattr(mcp_tool, "is_connected", False):
                        await mcp_tool.close()
                except Exception:
                    logger.debug("Non-critical: failed to close MCP tool on agent %s", agent.name)
            # Also close the agent's exit stack (covers tools entered during run)
            try:
                exit_stack = getattr(agent, "_async_exit_stack", None)
                if exit_stack is not None:
                    await exit_stack.aclose()
            except RuntimeError as e:
                if "cancel scope" in str(e).lower():
                    logger.debug("Suppressed cancel scope error closing agent %s", agent.name)
                else:
                    logger.debug("Non-critical: failed to close exit stack on agent %s", agent.name, exc_info=True)
            except Exception:
                logger.debug("Non-critical: failed to close exit stack on agent %s", agent.name, exc_info=True)

    # ── XCV propagation: always prefer the ContextVar (set by app.py) ──
    # The parent pipeline sets the XCV before calling run_investigation().
    # Using get_current_xcv() ensures we always inherit the parent XCV,
    # even if result.xcv was populated at a different time.
    contextvar_xcv = get_current_xcv()
    result_xcv = result.xcv if hasattr(result, 'xcv') and result.xcv else None
    xcv = contextvar_xcv or result_xcv or generate_xcv()
    logger.info(
        "Investigation XCV resolution: contextvar=%s, result.xcv=%s, chosen=%s",
        contextvar_xcv, result_xcv, xcv,
    )
    set_current_xcv(xcv)
    investigation.context.extra["xcv"] = xcv
    tracker = AgentLogger.get_instance()
    tracker.log_investigation_created(
        xcv=xcv,
        investigation_id=investigation.id,
        customer_name=result.customer_name,
        service_tree_id=result.service_tree_id,
        signal_count=len(result.all_activated_signals),
        compound_count=len(result.activated_compounds),
    )

    # Extract investigation agents
    orchestrator_name = inv_workflow_cfg["orchestrator_agent"]
    participant_names = inv_workflow_cfg.get("participants", [])

    tracker.log_workflow_started(
        xcv=xcv,
        workflow_type="InvestigationGroupChat",
        participants=participant_names,
    )
    max_turns = inv_workflow_cfg.get("max_turns", 30)

    if orchestrator_name not in all_agents_dict:
        logger.error("Investigation orchestrator '%s' not found in agents", orchestrator_name)
        return

    orchestrator = all_agents_dict[orchestrator_name]
    participants = [
        all_agents_dict[name]
        for name in participant_names
        if name in all_agents_dict and name != orchestrator_name
    ]

    missing = [n for n in participant_names if n not in all_agents_dict]
    if missing:
        logger.warning("Investigation participants not found: %s", missing)

    logger.info(
        "Building investigation GroupChat (orchestrator=%s, participants=%s, max_turns=%d)",
        orchestrator_name, [a.name for a in participants], max_turns,
    )

    # Termination condition: investigation_resolved signal or max turns.
    # NOTE: Only checks for termination signals — does NOT call parse_agent_output
    # with full logging, because that would emit a duplicate OutputParsed event
    # to App Insights. The event loop handles full parsing + apply_to_investigation.
    def termination_condition(messages: list[Message]) -> bool:
        assistant_count = sum(1 for m in messages if m.role == "assistant")
        if messages:
            last_text = messages[-1].text or ""
            last_name = getattr(messages[-1], "name", None) or "unknown"
            last_role = getattr(messages[-1], "role", "?")
            logger.info(
                "Termination check: msg_count=%d, assistant_count=%d, "
                "last_agent=%s, last_role=%s, text_len=%d",
                len(messages), assistant_count, last_name, last_role,
                len(last_text),
            )
            # Lightweight check: extract JSON block and look for investigation_resolved
            # without triggering a full parse_agent_output (which logs OutputParsed).
            json_block = extract_json_block(last_text)
            if json_block and isinstance(json_block, dict):
                sig_raw = json_block.get("signals", {})
                if isinstance(sig_raw, dict):
                    ir = sig_raw.get("investigation_resolved")
                    if ir is True or (isinstance(ir, str) and ir.lower() in ("true", "yes", "1")):
                        logger.info(
                            "Investigation resolved signal detected in termination check "
                            "(agent=%s, assistant_count=%d)",
                            last_name, assistant_count,
                        )
                        return True
            # Also check legacy ---SIGNALS--- for INVESTIGATION_RESOLVED
            if "---SIGNALS---" in last_text and "INVESTIGATION_RESOLVED" in last_text.upper():
                logger.info(
                    "Investigation resolved (legacy) detected in termination check "
                    "(agent=%s, assistant_count=%d)",
                    last_name, assistant_count,
                )
                return True

        if assistant_count >= max_turns:
            logger.info("Investigation max turns (%d) reached", max_turns)
            return True

        return False

    # Build workflow
    workflow = (
        GroupChatBuilder(
            participants=participants,
            orchestrator_agent=orchestrator,
            termination_condition=termination_condition,
            intermediate_outputs=True,
        )
        .build()
    )

    # Build task message (includes pre-computed stages)
    task = _build_task_message(investigation)
    investigation.phase = InvestigationPhase.TRIAGE

    # Set pipeline stage context for tool call distinction
    set_current_tool_stage(f"investigation:{investigation.phase.value}")

    # Reset middleware captures for this investigation
    if capture_mw:
        capture_mw.reset()
    if eval_mw:
        eval_mw.reset()
    if injection_mw:
        injection_mw.reset()
    if llm_log_mw:
        llm_log_mw.reset()

    yield {
        "type": "investigation_started",
        "investigation_id": investigation.id,
        "customer_name": result.customer_name,
        "service_tree_id": result.service_tree_id,
        "signal_count": len(result.all_activated_signals),
        "compound_count": len(result.activated_compounds),
    }

    # Run workflow and process events
    current_agent = orchestrator_name  # orchestrator runs first (speaker selection)
    agent_response_count = 0
    evidence_cycle_count = 0
    active_hypothesis_id = ""  # Track which hypothesis is being evaluated
    # Stall detection: warn every N seconds while waiting for a workflow event
    stall_warn_interval = inv_workflow_cfg.get("stall_warn_interval_seconds", 60)
    last_event_time = time.monotonic()
    workflow_start_time = time.monotonic()
    stall_warn_count = 0

    def _drain_tool_calls(agent_name: str) -> list[dict]:
        if not capture_mw:
            return []
        new = capture_mw.drain()
        return [{"tool": c["tool"], "query": c.get("query", ""),
                 "arguments": c.get("arguments", {}), "result": c.get("result"),
                 "error": c.get("error"), "duration_ms": c.get("duration_ms", 0),
                 "agent": c.get("agent", agent_name)} for c in new]

    # ── Queue-based event loop ──────────────────────────────────────
    # Read workflow events in a background task so the main loop can
    # yield stall warnings in real-time during long LLM calls.
    # Without this, the async generator blocks on __anext__() and
    # cannot yield anything — causing the SSE proxy to timeout.
    _event_q: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    async def _feed_workflow_events():
        """Background: iterate the GroupChat workflow and enqueue events."""
        try:
            async for evt in workflow.run(task, stream=True):
                await _event_q.put(evt)
        except Exception as exc:
            await _event_q.put(exc)
        finally:
            await _event_q.put(_SENTINEL)

    feeder_task = asyncio.create_task(_feed_workflow_events())

    try:
        event_count = 0
        while True:
            # Poll the queue with a timeout for stall detection.
            # On timeout, yield a stall warning immediately (keeps SSE alive).
            try:
                logger.debug(
                    "Waiting for workflow event #%d (agent=%s)",
                    event_count + 1, current_agent or "none",
                )
                item = await asyncio.wait_for(
                    _event_q.get(), timeout=stall_warn_interval,
                )
            except asyncio.TimeoutError:
                # No event for stall_warn_interval — yield warning NOW
                stall_warn_count += 1
                wait_secs = round(time.monotonic() - last_event_time, 1)
                stall_agent = current_agent or "unknown"
                llm_snapshot = llm_log_mw.drain() if llm_log_mw else []
                llm_detail = ""
                if llm_snapshot:
                    last_llm = llm_snapshot[-1]
                    llm_detail = (
                        f" LLM: model={last_llm.get('model', '?')}, "
                        f"error={last_llm.get('error', 'none')}, "
                        f"duration_ms={last_llm.get('duration_ms', '?')}"
                    )
                stall_msg = (
                    f"Investigation waiting: no workflow event for {wait_secs}s "
                    f"(warn #{stall_warn_count}). Active agent: {stall_agent}. "
                    f"Phase: {investigation.phase.value}.{llm_detail}"
                )
                logger.warning(stall_msg)
                tracker.log_investigation_error(
                    xcv=xcv,
                    investigation_id=investigation.id,
                    error=stall_msg,
                    phase=investigation.phase.value,
                )
                yield {
                    "type": "investigation_stall_warning",
                    "investigation_id": investigation.id,
                    "wait_seconds": wait_secs,
                    "warn_count": stall_warn_count,
                    "agent": stall_agent,
                    "phase": investigation.phase.value,
                    "llm_detail": llm_detail.strip(),
                }
                continue

            # Sentinel → workflow finished
            if item is _SENTINEL:
                logger.info(
                    "Workflow iterator exhausted: total_events=%d, agent_responses=%d, "
                    "last_agent=%s, elapsed=%.1fs",
                    event_count, agent_response_count, current_agent or "none",
                    time.monotonic() - workflow_start_time,
                )
                break
            # Exception from the feeder task
            if isinstance(item, Exception):
                raise item

            last_event_time = time.monotonic()
            stall_warn_count = 0
            event_count += 1
            event: WorkflowEvent = item

            # Log every event for diagnostics
            evt_type = getattr(event, "type", "?")
            evt_executor = getattr(event, "executor_id", None) or ""
            logger.info(
                "Workflow event #%d: type=%s, executor=%s",
                event_count, evt_type, evt_executor or "(none)",
            )

            # Track current agent from every event that carries executor_id,
            # so stall warnings show the real agent even before a response arrives.
            if hasattr(event, "executor_id") and event.executor_id:
                current_agent = event.executor_id

            # Handle executor lifecycle events (framework status events)
            if evt_type == "executor_invoked":
                logger.info("Agent invoked by framework: %s", evt_executor)
                continue
            if evt_type == "executor_completed":
                logger.info("Agent completed by framework: %s", evt_executor)
                continue

            if event.type == "output":
                data = event.data

                if isinstance(data, AgentResponseUpdate):
                    agent_name = event.executor_id or "unknown"

                    if agent_name != current_agent:
                        # Drain previous agent's middleware
                        _drain_tool_calls(current_agent or "unknown")

                        current_agent = agent_name
                        # Log agent invocation
                        tracker.log_agent_invoked(xcv, agent_name, task[:500])
                        if prompts and agent_name in prompts:
                            tracker.log_agent_prompt_used(xcv, agent_name, prompts[agent_name])

                        yield {
                            "type": "investigation_agent_start",
                            "agent": agent_name,
                            "phase": investigation.phase.value,
                            "investigation_id": investigation.id,
                        }

                    text = ""
                    if hasattr(data, "text") and data.text:
                        text = data.text

                    if text:
                        yield {
                            "type": "investigation_agent_chunk",
                            "agent": agent_name,
                            "text": text,
                        }

                elif isinstance(data, AgentResponse):
                    agent_name = event.executor_id or "unknown"
                    agent_response_count += 1
                    messages_text = []
                    for msg in data.messages:
                        if msg.text:
                            messages_text.append(msg.text)

                    full_text = "\n".join(messages_text)

                    if full_text:
                        # Track agent response
                        tracker.log_agent_response(xcv, agent_name, full_text)

                        # Drain middleware
                        tool_calls = _drain_tool_calls(agent_name)
                        llm_calls = llm_log_mw.drain() if llm_log_mw else []
                        injection_detections = injection_mw.drain() if injection_mw else []

                        # Track phase before parsing
                        prev_phase = investigation.phase.value

                        # Parse output and update investigation state
                        parsed = parse_agent_output(full_text, agent_name=agent_name)
                        apply_to_investigation(parsed, investigation)

                        # Track evidence cycles: reasoner requesting more evidence
                        if parsed.signals.needs_more_evidence:
                            evidence_cycle_count += 1
                            tracker.log_evidence_cycle(
                                xcv=xcv,
                                investigation_id=investigation.id,
                                cycle_number=evidence_cycle_count,
                                er_ids=[er.id for er in investigation.evidence if hasattr(er, 'id')],
                            )
                            logger.info(
                                "Evidence cycle %d detected (agent=%s, investigation=%s)",
                                evidence_cycle_count, agent_name, investigation.id,
                            )

                        # Log phase transition if changed
                        if investigation.phase.value != prev_phase:
                            tracker.log_phase_transition(
                                xcv=xcv,
                                investigation_id=investigation.id,
                                from_phase=prev_phase,
                                to_phase=investigation.phase.value,
                                agent_name=agent_name,
                            )

                        # Update tool stage context for subsequent tool calls
                        # Include hypothesis ID when in evidence-related phases
                        # Detect active hypothesis: first ACTIVE hypothesis in ranked order
                        _active_hyp = next(
                            (h for h in investigation.hypotheses
                             if h.status == HypothesisStatus.ACTIVE),
                            None,
                        )
                        _active_hyp_id = _active_hyp.id if _active_hyp else ""
                        if _active_hyp_id and _active_hyp_id != active_hypothesis_id:
                            active_hypothesis_id = _active_hyp_id
                            _rank = next(
                                (i for i, h in enumerate(investigation.hypotheses, 1)
                                 if h.id == active_hypothesis_id),
                                0,
                            )
                            tracker.log_hypothesis_selected(
                                xcv=xcv,
                                investigation_id=investigation.id,
                                hypothesis_id=active_hypothesis_id,
                                statement=_active_hyp.statement,
                                match_score=_active_hyp.match_score,
                                matched_symptoms=", ".join(getattr(_active_hyp, "matched_symptoms", []) or []),
                                evidence_needed=", ".join(getattr(_active_hyp, "evidence_needed", []) or []),
                                rank=_rank,
                                total_hypotheses=len(investigation.hypotheses),
                            )
                            yield {
                                "type": "hypothesis_evaluation_started",
                                "investigation_id": investigation.id,
                                "hypothesis_id": active_hypothesis_id,
                                "statement": _active_hyp.statement,
                                "match_score": _active_hyp.match_score,
                                "rank": _rank,
                                "total_hypotheses": len(investigation.hypotheses),
                            }

                        _stage = f"investigation:{investigation.phase.value}"
                        if investigation.hypotheses and investigation.phase in (
                            InvestigationPhase.PLANNING,
                            InvestigationPhase.COLLECTING,
                            InvestigationPhase.REASONING,
                        ):
                            _stage += f":{active_hypothesis_id or investigation.hypotheses[0].id}"
                        set_current_tool_stage(_stage)

                        yield {
                            "type": "investigation_agent_response",
                            "agent": agent_name,
                            "text": full_text,
                            "phase": investigation.phase.value,
                            "investigation_id": investigation.id,
                            "parsed_signals": {
                                "phase_complete": parsed.signals.phase_complete,
                                "next_agent": parsed.signals.next_agent,
                                "investigation_resolved": parsed.signals.investigation_resolved,
                                "needs_more_evidence": parsed.signals.needs_more_evidence,
                            },
                            "symptoms_count": len(investigation.symptoms),
                            "hypotheses_count": len(investigation.hypotheses),
                            "evidence_count": len(investigation.evidence),
                            "evidence_cycle_count": evidence_cycle_count,
                            "symptom_verdicts_summary": _symptom_verdicts_summary(investigation),
                            **({
                                "tool_calls": tool_calls
                            } if tool_calls else {}),
                            **({
                                "llm_calls": llm_calls
                            } if llm_calls else {}),
                            **({
                                "prompt_injection": injection_detections
                            } if injection_detections else {}),
                        }

                elif isinstance(data, list):
                    # Final conversation messages
                    pass

                else:
                    logger.info(
                        "Unhandled output data type: %s (executor=%s)",
                        type(data).__name__, evt_executor,
                    )

            elif evt_type == "error":
                # Framework-level error event — log and surface to UI
                error_data = getattr(event, "data", None)
                error_msg = str(error_data) if error_data else "Unknown workflow error"
                logger.error(
                    "Workflow error event: executor=%s, error=%s",
                    evt_executor, error_msg,
                )
                tracker.log_investigation_error(
                    xcv=xcv,
                    investigation_id=investigation.id,
                    error=f"Workflow error: {error_msg}",
                    phase=investigation.phase.value,
                )
                yield {
                    "type": "investigation_workflow_error",
                    "investigation_id": investigation.id,
                    "agent": evt_executor or current_agent or "unknown",
                    "error": error_msg,
                    "phase": investigation.phase.value,
                }

            else:
                # Log any other event types we don't handle yet
                logger.debug(
                    "Unhandled workflow event type=%s, executor=%s",
                    evt_type, evt_executor,
                )

    except Exception as exc:
        error_detail = str(exc)
        logger.exception("Investigation workflow failed for %s/%s: %s",
                         result.customer_name, result.service_tree_id, error_detail)
        tracker.log_investigation_error(
            xcv=xcv,
            investigation_id=investigation.id,
            error=error_detail,
            phase=investigation.phase.value,
        )
        tracker.log_request_end(xcv, status="error", error=error_detail)
        yield {
            "type": "investigation_error",
            "investigation_id": investigation.id,
            "error": f"Investigation workflow failed: {error_detail}",
            "phase": investigation.phase.value,
            "last_agent": current_agent or "unknown",
        }
        if not feeder_task.done():
            feeder_task.cancel()
        await _close_all_agents()
        return

    # ── Post-workflow diagnostics ──────────────────────────────
    total_workflow_dur = round(time.monotonic() - workflow_start_time, 1)

    # Drain LLM middleware to capture any errors from the final (or only) LLM call
    final_llm_calls = llm_log_mw.drain() if llm_log_mw else []
    llm_errors = [c for c in final_llm_calls if c.get("error")]
    if llm_errors:
        for lc in llm_errors:
            logger.error(
                "LLM call error detected: agent=%s, model=%s, error=%s, duration_ms=%s",
                lc.get("agent", "?"), lc.get("model", "?"),
                lc.get("error", "?"), lc.get("duration_ms", "?"),
            )

    logger.info(
        "Investigation workflow loop ended: agent_responses=%d, events=%d, "
        "phase=%s, last_agent=%s, total_time=%.1fs, llm_calls=%d, llm_errors=%d",
        agent_response_count, event_count, investigation.phase.value,
        current_agent or "none", total_workflow_dur,
        len(final_llm_calls), len(llm_errors),
    )

    # Detect silent workflow failure: the framework may swallow LLM errors
    # and terminate the GroupChat without raising.  If zero agent responses
    # were produced, something went wrong.
    if agent_response_count == 0:
        # Build a diagnostic message from whatever the LLM middleware captured
        diag_parts = [
            "Investigation workflow produced 0 agent responses "
            f"(total_time={total_workflow_dur}s, events={event_count})."
        ]
        if llm_errors:
            for lc in llm_errors:
                diag_parts.append(
                    f"  LLM error: agent={lc.get('agent')}, model={lc.get('model')}, "
                    f"error={lc.get('error')}, duration_ms={lc.get('duration_ms')}"
                )
        elif final_llm_calls:
            # LLM call succeeded but framework didn't produce a response
            for lc in final_llm_calls:
                diag_parts.append(
                    f"  LLM call: agent={lc.get('agent')}, model={lc.get('model')}, "
                    f"finish_reason={lc.get('finish_reason')}, "
                    f"duration_ms={lc.get('duration_ms')}, "
                    f"tokens={lc.get('total_tokens')}"
                )
        else:
            diag_parts.append(
                "  No LLM calls captured — the framework may not have dispatched any."
            )

        warning = "\n".join(diag_parts)
        logger.warning(warning)
        tracker.log_investigation_error(
            xcv=xcv,
            investigation_id=investigation.id,
            error=warning,
            phase=investigation.phase.value,
        )
        tracker.log_request_end(xcv, status="error", error=warning)
        yield {
            "type": "investigation_error",
            "investigation_id": investigation.id,
            "error": warning,
        }
        await _close_all_agents()
        return

    # Mark complete
    if investigation.phase != InvestigationPhase.COMPLETE:
        investigation.phase = InvestigationPhase.COMPLETE
    investigation.completed_at = datetime.now(timezone.utc).isoformat()

    # Clear tool stage context — investigation is done
    set_current_tool_stage(None)

    yield {
        "type": "investigation_complete",
        "investigation_id": investigation.id,
        "phase": investigation.phase.value,
        "symptoms_count": len(investigation.symptoms),
        "hypotheses_count": len(investigation.hypotheses),
        "evidence_count": len(investigation.evidence),
        "actions_count": len(investigation.actions),
        "evidence_cycles": investigation.evidence_cycles,
        "duration_seconds": _duration_seconds(investigation),
        "symptom_verdicts_summary": _symptom_verdicts_summary(investigation),
    }

    # Log investigation complete
    tracker.log_investigation_complete(
        xcv=xcv,
        investigation_id=investigation.id,
        symptoms_count=len(investigation.symptoms),
        hypotheses_count=len(investigation.hypotheses),
        evidence_count=len(investigation.evidence),
        actions_count=len(investigation.actions),
        evidence_cycles=investigation.evidence_cycles,
        duration_seconds=_duration_seconds(investigation),
    )
    tracker.log_request_end(xcv, status="complete")

    # ── Clean up feeder task and MCP connections ─────────────────────
    if not feeder_task.done():
        feeder_task.cancel()
    await _close_all_agents()


def _duration_seconds(investigation: Investigation) -> float:
    """Calculate investigation duration in seconds."""
    try:
        start = datetime.fromisoformat(investigation.started_at)
        end = datetime.fromisoformat(investigation.completed_at) if investigation.completed_at else datetime.now(timezone.utc)
        return (end - start).total_seconds()
    except (ValueError, TypeError):
        return 0.0


def _symptom_verdicts_summary(investigation: Investigation) -> dict:
    """Aggregate symptom verdict counts across all hypotheses."""
    from .investigation_state import SymptomVerdict

    totals: dict[str, int] = {v.value: 0 for v in SymptomVerdict}
    per_hyp: dict[str, dict[str, int]] = {}
    for hyp in investigation.hypotheses:
        if not hyp.symptom_verdicts:
            continue
        counts = {v.value: 0 for v in SymptomVerdict}
        for sv in hyp.symptom_verdicts.values():
            counts[sv.value] = counts.get(sv.value, 0) + 1
            totals[sv.value] = totals.get(sv.value, 0) + 1
        per_hyp[hyp.id] = counts
    return {"totals": totals, "per_hypothesis": per_hyp}


async def on_group_chat_callback(result: SignalBuilderResult) -> None:
    """Convenience callback for signal_builder's run_signal_builder_loop.

    Consumes the async iterator from run_investigation and logs events.
    In production, this would be replaced with an SSE/websocket emitter.
    """
    async for event in run_investigation(result):
        event_type = event.get("type", "unknown")

        if event_type == "investigation_started":
            logger.info(
                "Investigation %s started for %s/%s (%d signals, %d compounds)",
                event["investigation_id"],
                event["customer_name"],
                event["service_tree_id"],
                event["signal_count"],
                event["compound_count"],
            )

        elif event_type == "investigation_agent_response":
            logger.info(
                "[%s] %s responded (phase=%s, signals=%s)",
                event["investigation_id"],
                event["agent"],
                event["phase"],
                event["parsed_signals"],
            )

        elif event_type == "investigation_complete":
            logger.info(
                "Investigation %s complete: %d symptoms, %d hypotheses, %d evidence, %d actions (%.1fs)",
                event["investigation_id"],
                event["symptoms_count"],
                event["hypotheses_count"],
                event["evidence_count"],
                event["actions_count"],
                event["duration_seconds"],
            )

        elif event_type == "investigation_error":
            logger.error(
                "Investigation %s error: %s",
                event["investigation_id"],
                event.get("error"),
            )
