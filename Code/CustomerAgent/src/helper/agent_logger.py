"""
Agent Logger — end-to-end traceability for MAF GroupChat workflows.

Every user request gets a unique XCV / cross-correlation vector (UUID). All
activities—agent invocations, tool calls, MCP operations, and final
responses—are logged to Azure Application Insights as custom events with the
XCV as the shared correlation key.

Usage:
    tracker = AgentLogger.get_instance()
    tracker.log_request_start(xcv, query)
    tracker.log_agent_invoked(xcv, agent_name, input_text)
    ...
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from typing import Any

# from opentelemetry.trace import StatusCode  # [Custom Foundry spans — commented out]

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger(__name__)

# ── Feature flag: set ENABLE_AGENT_LOGGING=false to disable all logging ──────
_LOGGING_ENABLED = os.getenv("ENABLE_AGENT_LOGGING", "true").strip().lower() in ("true", "1", "yes")

# ── Global feature flag: set LOG_AGENT_CONTENT=false to redact agent/tool output ────
_LOG_CONTENT = os.getenv("LOG_AGENT_CONTENT", "true").strip().lower() in ("true", "1", "yes")
_REDACTED = "[REDACTED]"
# Max chars for logged content. 0 = no truncation.
_LOG_MAX_CHARS = int(os.getenv("LOG_MAX_CHARS", "0"))

# ── Foundry tracing: set ENABLE_FOUNDRY_TRACING=true to emit OTel spans ──────
# Spans are exported to the same App Insights resource and appear in the
# Foundry portal → Tracing view as hierarchical traces.
_FOUNDRY_TRACING_ENABLED = os.getenv("ENABLE_FOUNDRY_TRACING", "false").strip().lower() in ("true", "1", "yes")

# ── Per-agent content logging overrides loaded from agents_config.json ───────
# Each entry: { "log_input": bool, "log_output": bool }
_AGENT_LOG_OVERRIDES: dict[str, dict[str, bool]] = {}


def _load_agent_log_config() -> None:
    """Load per-agent log_input / log_output flags from agents_config.json."""
    global _AGENT_LOG_OVERRIDES
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "agents", "agents_config.json"
    )
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        for agent in data.get("agents", []):
            name = agent.get("name", "")
            if name:
                _AGENT_LOG_OVERRIDES[name] = {
                    "log_input": agent.get("log_input", _LOG_CONTENT),
                    "log_output": agent.get("log_output", _LOG_CONTENT),
                }
        logger.info(
            "Loaded per-agent log config for %d agents", len(_AGENT_LOG_OVERRIDES)
        )
    except Exception as exc:
        logger.warning("Could not load agents_config.json for log config: %s", exc)


_load_agent_log_config()

# ── Context variable for per-request XCV propagation ─────────────────────────
_current_xcv: ContextVar[str | None] = ContextVar(
    "current_xcv", default=None
)
# ── Context variable for pipeline stage (tool call distinction) ───────
# Values: "signal_building", "investigation:<phase>" (e.g. "investigation:collecting")
# Optionally suffixed with hypothesis: "investigation:collecting:HYP-001"
_current_tool_stage: ContextVar[str | None] = ContextVar(
    "current_tool_stage", default=None
)

def get_current_xcv() -> str | None:
    """Return the XCV bound to the current async context."""
    return _current_xcv.get()


def set_current_xcv(xcv: str) -> None:
    """Bind an XCV to the current async context."""
    _current_xcv.set(xcv)


def get_current_tool_stage() -> str | None:
    """Return the pipeline stage bound to the current async context."""
    return _current_tool_stage.get()


def set_current_tool_stage(stage: str | None) -> None:
    """Bind a pipeline stage to the current async context.

    Values: 'signal_building', 'investigation:<phase>', 'investigation:<phase>:<hypothesis_id>'
    Pass None to clear.
    """
    _current_tool_stage.set(stage)


def generate_xcv() -> str:
    """Generate a new unique XCV (UUID4)."""
    return str(uuid.uuid4())


# ── Real-time UI event queue ─────────────────────────────────────────────────
# Allows the UI to subscribe to a live stream of AgentLogger events for a
# specific XCV.  The /api/run endpoint subscribes before kicking off the
# signal builder pipeline; every _emit() call pushes a copy of the event
# into the subscriber's asyncio.Queue so it can be yielded as SSE.
#
# Lifecycle:
#   1. UI calls POST /api/run → backend calls subscribe_events(xcv)
#   2. Pipeline runs; every _emit() pushes to the queue
#   3. SSE generator drains the queue; when pipeline ends it calls
#      unsubscribe_events(xcv) to clean up.
_event_subscribers: dict[str, asyncio.Queue] = {}


def subscribe_events(xcv: str) -> asyncio.Queue:
    """Create a real-time event queue for the given XCV.

    Returns an asyncio.Queue that will receive every AgentLogger event
    (as a dict) emitted under this XCV.  The caller should drain the
    queue and forward items as SSE data frames.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=5000)
    _event_subscribers[xcv] = q
    logger.debug("UI event subscriber registered for xcv=%s", xcv[:8])
    return q


def unsubscribe_events(xcv: str) -> None:
    """Remove the event queue for the given XCV.

    Call this when the SSE stream ends (investigation complete or client
    disconnect) to avoid leaking memory.
    """
    removed = _event_subscribers.pop(xcv, None)
    if removed:
        logger.debug("UI event subscriber removed for xcv=%s", xcv[:8])

#------- UI Specific ─────────────────────────────────────────────────
class AgentLogger:
    """Singleton tracker that logs structured events to Application Insights
    and (optionally) emits OTel spans for Microsoft Foundry tracing."""

    _instance: "AgentLogger | None" = None

    def __init__(self) -> None:
        # ── Application Insights (log records) ────────────────────────────
        self._tc = None
        self._provider = None
        # ── Foundry tracing (OTel spans) — custom spans commented out ────
        # self._tracer = None
        # self._trace_provider = None
        # self._request_spans: dict[str, Any] = {}   # xcv → active request span
        # self._agent_spans: dict[str, Any] = {}     # xcv → active agent span

        self._init_app_insights()
        # self._init_foundry_tracing()  # [Custom Foundry spans — replaced by SDK]
        self._init_sdk_observability()

    @classmethod
    def get_instance(cls) -> "AgentLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_app_insights(self) -> None:
        """Initialize the Application Insights telemetry client."""
        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
        if not connection_string:
            logger.warning(
                "APPLICATIONINSIGHTS_CONNECTION_STRING not set; "
                "agent logging will log to Python logger only."
            )
            return

        try:
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter

            # Set up a dedicated logger that exports to App Insights
            ai_logger = logging.getLogger("agent_logger.appinsights")
            ai_logger.setLevel(logging.INFO)

            # Avoid duplicate handlers on re-init
            if not any(isinstance(h, LoggingHandler) for h in ai_logger.handlers):
                exporter = AzureMonitorLogExporter(connection_string=connection_string)
                provider = LoggerProvider()
                provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
                handler = LoggingHandler(level=logging.INFO, logger_provider=provider)
                ai_logger.addHandler(handler)
                self._provider = provider

            self._tc = ai_logger
            logger.info("Application Insights tracker initialized (OpenTelemetry)")
        except ImportError:
            logger.warning(
                "opentelemetry/azure-monitor packages not installed; "
                "install azure-monitor-opentelemetry-exporter for App Insights logging."
            )
        except Exception as exc:
            logger.warning("Failed to initialize App Insights: %s", exc)

    # ── SDK built-in observability ────────────────────────────────────────

    def _init_sdk_observability(self) -> None:
        """Enable the MAF SDK's built-in OpenTelemetry instrumentation.

        The SDK automatically emits GenAI semantic-convention spans, logs,
        and metrics for every agent invoke, chat completion, tool execution,
        and workflow step.  Spans are exported to the same App Insights
        resource and appear in the Foundry portal → Tracing view.

        Controlled by the ENABLE_FOUNDRY_TRACING env var.
        """
        if not _FOUNDRY_TRACING_ENABLED:
            logger.info("Foundry tracing disabled (ENABLE_FOUNDRY_TRACING != true)")
            return

        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
        if not connection_string:
            logger.warning(
                "Foundry tracing enabled but APPLICATIONINSIGHTS_CONNECTION_STRING "
                "not set; SDK spans will not be exported."
            )
            return

        try:
            from agent_framework.observability import configure_otel_providers
            from azure.monitor.opentelemetry.exporter import (
                AzureMonitorTraceExporter,
                AzureMonitorLogExporter,
            )

            configure_otel_providers(
                exporters=[
                    AzureMonitorTraceExporter(connection_string=connection_string),
                    AzureMonitorLogExporter(connection_string=connection_string),
                ],
                enable_sensitive_data=_LOG_CONTENT,
            )
            logger.info(
                "SDK observability initialized "
                "(configure_otel_providers → App Insights + Foundry)"
            )
        except ImportError:
            logger.warning(
                "SDK observability: agent_framework.observability or "
                "azure-monitor-opentelemetry-exporter not installed."
            )
        except Exception as exc:
            logger.warning("Failed to initialize SDK observability: %s", exc)

    # ── Custom Foundry span code (commented out — replaced by SDK) ───────
    #
    # def _init_foundry_tracing(self) -> None:
    #     """Initialize OTel TracerProvider for Foundry span export."""
    #     if not _FOUNDRY_TRACING_ENABLED:
    #         return
    #     connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    #     if not connection_string:
    #         return
    #     try:
    #         from opentelemetry import trace
    #         from opentelemetry.sdk.trace import TracerProvider
    #         from opentelemetry.sdk.trace.export import BatchSpanProcessor
    #         from opentelemetry.sdk.resources import Resource
    #         from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
    #         resource = Resource.create({"service.name": "AGENT_SERVER"})
    #         tracer_provider = TracerProvider(resource=resource)
    #         tracer_provider.add_span_processor(
    #             BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=connection_string))
    #         )
    #         trace.set_tracer_provider(tracer_provider)
    #         self._trace_provider = tracer_provider
    #         self._tracer = trace.get_tracer("agent_logger")
    #     except Exception as exc:
    #         logger.warning("Failed to initialize Foundry tracing: %s", exc)
    #
    # def _start_request_span(self, xcv, query): ...
    # def _end_request_span(self, xcv, status="complete", error=""): ...
    # def _start_agent_span(self, xcv, agent_name): ...
    # def _end_agent_span(self, xcv): ...
    # def _add_tool_span(self, xcv, agent_name, tool_name, duration_ms, error=""): ...
    # def _add_llm_span(self, xcv, agent_name, model, input_tokens, output_tokens, duration_ms, error=""): ...

    def flush(self, timeout_millis: int = 5000) -> None:
        """Force-flush pending telemetry."""
        # Application Insights: flush log records
        if self._provider:
            self._provider.force_flush(timeout_millis)
        # SDK observability: flush is handled by the SDK's own providers
        # (configured in configure_otel_providers). No manual flush needed.
        # # [Custom Foundry spans — commented out]
        # if self._trace_provider:
        #     self._trace_provider.force_flush(timeout_millis)

    def _emit(self, event_name: str, xcv: str, properties: dict[str, Any]) -> None:
        """Emit a structured event to App Insights and to the Python logger.

        If a UI subscriber is registered for this XCV (via subscribe_events),
        the event is also pushed into the subscriber's asyncio.Queue so the
        SSE endpoint can stream it to the browser in real time.
        """
        if not _LOGGING_ENABLED:
            return

        props = {
            "xcv": xcv,
            "EventName": event_name,
            "Service": "AGENT_SERVER",
            **properties,
        }

        # Always log locally
        logger.info("[%s] %s | %s | %s", xcv[:8], "AGENT_SERVER", event_name, _safe_summary(props))

        # Send to App Insights if configured
        if self._tc:
            # Build message: "EventName | Service | [Tool/Agent] | XCV"
            entity = properties.get("Tool") or properties.get("Agent") or ""
            if entity:
                msg = "%s | %s | %s | %s"
                args = (event_name, "AGENT_SERVER", entity, xcv)
            else:
                msg = "%s | %s | %s"
                args = (event_name, "AGENT_SERVER", xcv)
            self._tc.info(msg, *args, extra=props)

        # ── Push to real-time UI subscriber queues ─────────────────────
        # Broadcast to ALL active subscribers regardless of XCV, because
        # the pipeline spawns child XCVs (evaluate_signals generates one
        # per target, investigation_runner generates another) but the UI
        # subscriber is registered under the parent /api/run XCV.
        # This is non-blocking: if a queue is full we drop the event
        # rather than stalling the pipeline.
        if _event_subscribers:
            ui_event = {
                "type": event_name,
                "timestamp": time.time(),
                "source_xcv": xcv,
                **properties,
            }
            for sub_xcv, subscriber_queue in _event_subscribers.items():
                try:
                    subscriber_queue.put_nowait(ui_event)
                except asyncio.QueueFull:
                    logger.warning(
                        "UI event queue full for xcv=%s, dropping event %s",
                        sub_xcv[:8], event_name,
                    )

    # ---UI specific─────────────────────────────────────────────────
    # ── Lifecycle events ─────────────────────────────────────────────────

    def log_request_start(self, xcv: str, query: str, user: str = "") -> None:
        self._emit("RequestStart", xcv, {
            "Query": query,
            "User": user,
        })
        # [Custom Foundry spans — commented out; SDK emits spans automatically]
        # self._start_request_span(xcv, query)

    def log_agents_loaded(self, xcv: str, agent_names: list[str]) -> None:
        self._emit("AgentsLoaded", xcv, {
            "AgentCount": len(agent_names),
            "Agents": ", ".join(agent_names),
        })

    def log_workflow_started(self, xcv: str, workflow_type: str, participants: list[str]) -> None:
        self._emit("WorkflowStarted", xcv, {
            "WorkflowType": workflow_type,
            "Participants": ", ".join(participants),
        })

    def log_prompt_loaded(self, agent_name: str, prompt_file: str, prompt_content: str) -> None:
        lo = _should_log_output(agent_name)
        self._emit("PromptLoaded", "STARTUP", {
            "Agent": agent_name,
            "PromptFile": prompt_file,
            "PromptContent": _redact(prompt_content, log_content=lo),
            "Length": len(prompt_content),
        })

    # ── Agent events ─────────────────────────────────────────────────────

    def log_agent_invoked(self, xcv: str, agent_name: str, input_text: str) -> None:
        li = _should_log_input(agent_name)
        self._emit("AgentInvoked", xcv, {
            "Agent": agent_name,
            "InputText": _redact(input_text, log_content=li),
        })
        # [Custom Foundry spans — commented out; SDK emits spans automatically]
        # self._start_agent_span(xcv, agent_name)

    def log_agent_prompt_used(self, xcv: str, agent_name: str, prompt_content: str) -> None:
        li = _should_log_input(agent_name)
        self._emit("AgentPromptUsed", xcv, {
            "Agent": agent_name,
            "PromptContent": _redact(prompt_content, log_content=li),
            "Length": len(prompt_content),
        })

    def log_agent_response(
        self,
        xcv: str,
        agent_name: str,
        output_text: str,
        duration_ms: float = 0,
    ) -> None:
        lo = _should_log_output(agent_name)
        self._emit("AgentResponse", xcv, {
            "Agent": agent_name,
            "OutputText": _redact(output_text, log_content=lo),
            "DurationMs": round(duration_ms, 1),
        })
        # [Custom Foundry spans — commented out; SDK emits spans automatically]
        # self._end_agent_span(xcv)

    # ── LLM call events ────────────────────────────────────────────────

    def log_llm_call(
        self,
        xcv: str,
        agent_name: str,
        model: str,
        message_count: int,
        response_text: str = "",
        finish_reason: str = "",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float = 0,
        error: str = "",
    ) -> None:
        lo = _should_log_output(agent_name)
        self._emit("LLMCall", xcv, {
            "Agent": agent_name,
            "Model": model,
            "MessageCount": message_count,
            "ResponseText": _redact(response_text, log_content=lo),
            "FinishReason": finish_reason,
            "InputTokens": input_tokens or 0,
            "OutputTokens": output_tokens or 0,
            "TotalTokens": total_tokens or 0,
            "DurationMs": round(duration_ms, 1),
            "Error": error,
        })
        # [Custom Foundry spans — commented out; SDK emits spans automatically]
        # self._add_llm_span(xcv, agent_name, model, input_tokens or 0, output_tokens or 0, duration_ms, error)

    # ── Evaluation API events ────────────────────────────────────────────

    def log_eval_api_call(
        self,
        xcv: str,
        agent_name: str,
        api_url: str,
        input_text: str,
        output_text: str,
        http_status: int | None = None,
        response_body: str = "",
        score: Any = None,
        feedback: str = "",
        duration_ms: float = 0,
        error: str = "",
    ) -> None:
        li = _should_log_input(agent_name)
        lo = _should_log_output(agent_name)
        self._emit("EvalApiCall", xcv, {
            "Agent": agent_name,
            "ApiUrl": api_url,
            "InputText": _redact(input_text, log_content=li),
            "OutputText": _redact(output_text, log_content=li),
            "HttpStatus": http_status or 0,
            "ResponseBody": _redact(response_body, log_content=lo),
            "Score": score if score is not None else "",
            "Feedback": _redact(feedback, log_content=lo),
            "DurationMs": round(duration_ms, 1),
            "Error": error,
        })

    # ── Prompt Injection API events ──────────────────────────────────────

    def log_injection_api_call(
        self,
        xcv: str,
        agent_name: str,
        api_url: str,
        input_text: str,
        http_status: int | None = None,
        response_body: str = "",
        is_injection: bool = False,
        confidence: float = 0,
        category: str = "",
        duration_ms: float = 0,
        error: str = "",
    ) -> None:
        li = _should_log_input(agent_name)
        lo = _should_log_output(agent_name)
        self._emit("InjectionApiCall", xcv, {
            "Agent": agent_name,
            "ApiUrl": api_url,
            "InputText": _redact(input_text, log_content=li),
            "HttpStatus": http_status or 0,
            "ResponseBody": _redact(response_body, log_content=lo),
            "IsInjection": is_injection,
            "Confidence": confidence,
            "Category": category,
            "DurationMs": round(duration_ms, 1),
            "Error": error,
        })

    # ── Tool / MCP events ────────────────────────────────────────────────

    def log_tool_call(
        self,
        xcv: str,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: str | None = None,
        error: str | None = None,
        duration_ms: float = 0,
    ) -> None:
        li = _should_log_input(agent_name)
        lo = _should_log_output(agent_name)
        # Derive pipeline stage from context variable
        stage = get_current_tool_stage() or ""
        stage_label = ""
        hypothesis_id = ""
        if stage.startswith("investigation:"):
            parts = stage.split(":", 2)
            stage_label = f"investigation:{parts[1]}" if len(parts) >= 2 else "investigation"
            hypothesis_id = parts[2] if len(parts) >= 3 else ""
        elif stage:
            stage_label = stage
        self._emit("ToolCall", xcv, {
            "Agent": agent_name,
            "Tool": tool_name,
            "Stage": stage_label,
            "HypothesisId": hypothesis_id,
            "Arguments": _redact(str(arguments), log_content=li),
            "Result": _redact(result or "", log_content=lo),
            "Error": error or "",
            "DurationMs": round(duration_ms, 1),
        })
        # [Custom Foundry spans — commented out; SDK emits spans automatically]
        # self._add_tool_span(xcv, agent_name, tool_name, duration_ms, error or "")

    # ── Final response ───────────────────────────────────────────────────

    def log_final_response(
        self,
        xcv: str,
        agent_outputs_count: int,
        final_summary: str = "",
    ) -> None:
        self._emit("FinalResponse", xcv, {
            "AgentOutputsCount": agent_outputs_count,
            "FinalSummary": _redact(final_summary),
        })

    def log_request_end(
        self,
        xcv: str,
        status: str = "complete",
        error: str = "",
    ) -> None:
        self._emit("RequestEnd", xcv, {
            "Status": status,
            "Error": error,
        })
        # [Custom Foundry spans — commented out; SDK emits spans automatically]
        # self._end_agent_span(xcv)
        # self._end_request_span(xcv, status, error)

    # ── Investigation pipeline events ────────────────────────────────────

    def log_signal_evaluation_start(
        self,
        xcv: str,
        customer_name: str,
        service_tree_id: str,
        service_name: str = "",
    ) -> None:
        self._emit("SignalEvaluationStart", xcv, {
            "CustomerName": customer_name,
            "ServiceTreeId": service_tree_id,
            "ServiceName": service_name,
        })

    def log_mcp_collection_call(
        self,
        xcv: str,
        tool_name: str,
        parameters: dict[str, Any],
        row_count: int,
        duration_ms: float = 0,
        error: str = "",
        service_name: str = "",
    ) -> None:
        self._emit("MCPCollectionCall", xcv, {
            "Tool": tool_name,
            "Parameters": _redact(str(parameters)),
            "RowCount": row_count,
            "DurationMs": round(duration_ms, 1),
            "Error": error,
            "ServiceName": service_name,
        })

    def log_signal_type_evaluated(
        self,
        xcv: str,
        signal_type_id: str,
        signal_name: str,
        has_data: bool,
        row_count: int,
        activated_count: int,
        max_strength: float,
        best_confidence: str,
        activated_slis: list[str] | None = None,
    ) -> None:
        props: dict[str, Any] = {
            "SignalTypeId": signal_type_id,
            "SignalName": signal_name,
            "HasData": has_data,
            "RowCount": row_count,
            "ActivatedCount": activated_count,
            "MaxStrength": round(max_strength, 4),
            "BestConfidence": best_confidence,
        }
        if activated_slis:
            props["ActivatedSLIs"] = ", ".join(activated_slis)
        self._emit("SignalTypeEvaluated", xcv, props)

    def log_compound_evaluated(
        self,
        xcv: str,
        compound_id: str,
        compound_name: str,
        activated: bool,
        strength: float,
        contributing_types: list[str],
        confidence: str = "",
        rationale: str = "",
    ) -> None:
        self._emit("CompoundEvaluated", xcv, {
            "CompoundId": compound_id,
            "CompoundName": compound_name,
            "Activated": activated,
            "Strength": round(strength, 4),
            "ContributingTypes": ", ".join(contributing_types),
            "Confidence": confidence,
            "Rationale": rationale,
        })

    def log_signal_decision(
        self,
        xcv: str,
        customer_name: str,
        service_tree_id: str,
        action: str,
        signal_count: int,
        compound_count: int,
    ) -> None:
        self._emit("SignalDecision", xcv, {
            "CustomerName": customer_name,
            "ServiceTreeId": service_tree_id,
            "Action": action,
            "SignalCount": signal_count,
            "CompoundCount": compound_count,
        })

    def log_symptom_templates_loaded(
        self,
        xcv: str,
        template_count: int,
        template_ids: list[str],
    ) -> None:
        self._emit("SymptomTemplatesLoaded", xcv, {
            "TemplateCount": template_count,
            "TemplateIds": ", ".join(template_ids[:20]),
        })

    def log_hypothesis_scoring(
        self,
        xcv: str,
        input_symptom_count: int,
        output_hypothesis_count: int,
        top_hypothesis_id: str = "",
        top_score: float = 0.0,
        all_scores: str = "",
    ) -> None:
        self._emit("HypothesisScoring", xcv, {
            "InputSymptomCount": input_symptom_count,
            "OutputHypothesisCount": output_hypothesis_count,
            "TopHypothesisId": top_hypothesis_id,
            "TopScore": round(top_score, 4),
            "AllScores": _redact(all_scores),
        })

    def log_investigation_created(
        self,
        xcv: str,
        investigation_id: str,
        customer_name: str,
        service_tree_id: str,
        signal_count: int,
        compound_count: int,
    ) -> None:
        self._emit("InvestigationCreated", xcv, {
            "InvestigationId": investigation_id,
            "CustomerName": customer_name,
            "ServiceTreeId": service_tree_id,
            "SignalCount": signal_count,
            "CompoundCount": compound_count,
        })

    def log_phase_transition(
        self,
        xcv: str,
        investigation_id: str,
        from_phase: str,
        to_phase: str,
        agent_name: str = "",
    ) -> None:
        self._emit("PhaseTransition", xcv, {
            "InvestigationId": investigation_id,
            "FromPhase": from_phase,
            "ToPhase": to_phase,
            "Agent": agent_name,
        })

    def log_output_parsed(
        self,
        xcv: str,
        agent_name: str,
        is_json_parsed: bool,
        phase_complete: str = "",
        next_agent: str = "",
        investigation_resolved: bool = False,
        needs_more_evidence: bool = False,
        hypothesis_refuted: bool = False,
        symptoms_count: int = 0,
        hypotheses_count: int = 0,
        evaluations_count: int = 0,
        evidence_items_count: int = 0,
        actions_count: int = 0,
        raw_output: str = "",
    ) -> None:
        lo = _should_log_output(agent_name)
        self._emit("OutputParsed", xcv, {
            "Agent": agent_name,
            "IsJsonParsed": is_json_parsed,
            "PhaseComplete": phase_complete or "",
            "NextAgent": next_agent or "",
            "InvestigationResolved": investigation_resolved,
            "NeedsMoreEvidence": needs_more_evidence,
            "HypothesisRefuted": hypothesis_refuted,
            "SymptomsCount": symptoms_count,
            "HypothesesCount": hypotheses_count,
            "EvaluationsCount": evaluations_count,
            "EvidenceItemsCount": evidence_items_count,
            "ActionsCount": actions_count,
            "RawOutput": _redact(raw_output, log_content=lo),
        })

    def log_speaker_selected(
        self,
        xcv: str,
        last_speaker: str,
        next_speaker: str,
        reason: str,
        evidence_cycle: int = 0,
        hypothesis_cycle: int = 0,
    ) -> None:
        self._emit("SpeakerSelected", xcv, {
            "LastSpeaker": last_speaker,
            "NextSpeaker": next_speaker,
            "Reason": reason,
            "EvidenceCycle": evidence_cycle,
            "HypothesisCycle": hypothesis_cycle,
        })

    def log_evidence_cycle(
        self,
        xcv: str,
        investigation_id: str,
        cycle_number: int,
        er_ids: list[str],
    ) -> None:
        self._emit("EvidenceCycle", xcv, {
            "InvestigationId": investigation_id,
            "CycleNumber": cycle_number,
            "ERIds": ", ".join(er_ids),
        })

    def log_hypothesis_transition(
        self,
        xcv: str,
        investigation_id: str,
        hypothesis_id: str,
        old_status: str,
        new_status: str,
        confidence: float = 0.0,
    ) -> None:
        self._emit("HypothesisTransition", xcv, {
            "InvestigationId": investigation_id,
            "HypothesisId": hypothesis_id,
            "OldStatus": old_status,
            "NewStatus": new_status,
            "Confidence": round(confidence, 4),
        })

    def log_hypothesis_selected(
        self,
        xcv: str,
        investigation_id: str,
        hypothesis_id: str,
        statement: str = "",
        match_score: float = 0.0,
        matched_symptoms: str = "",
        evidence_needed: str = "",
        rank: int = 0,
        total_hypotheses: int = 0,
    ) -> None:
        """Emit when a hypothesis is selected for evaluation."""
        self._emit("HypothesisSelected", xcv, {
            "InvestigationId": investigation_id,
            "HypothesisId": hypothesis_id,
            "Statement": statement,
            "MatchScore": round(match_score, 4),
            "MatchedSymptoms": matched_symptoms,
            "EvidenceNeeded": evidence_needed,
            "Rank": rank,
            "TotalHypotheses": total_hypotheses,
        })

    def log_investigation_error(
        self,
        xcv: str,
        investigation_id: str,
        error: str,
        phase: str = "",
    ) -> None:
        self._emit("InvestigationError", xcv, {
            "InvestigationId": investigation_id,
            "Error": error,
            "Phase": phase,
        })

    def log_investigation_complete(
        self,
        xcv: str,
        investigation_id: str,
        symptoms_count: int,
        hypotheses_count: int,
        evidence_count: int,
        actions_count: int,
        evidence_cycles: int,
        duration_seconds: float,
    ) -> None:
        self._emit("InvestigationComplete", xcv, {
            "InvestigationId": investigation_id,
            "SymptomsCount": symptoms_count,
            "HypothesesCount": hypotheses_count,
            "EvidenceCount": evidence_count,
            "ActionsCount": actions_count,
            "EvidenceCycles": evidence_cycles,
            "DurationSeconds": round(duration_seconds, 1),
        })


# ── Helpers ──────────────────────────────────────────────────────────────────

def _redact(text: str, max_len: int | None = None, log_content: bool | None = None) -> str:
    """Return truncated text if content logging is enabled, else '[REDACTED]'.

    Args:
        max_len: Override char limit. None → use LOG_MAX_CHARS env (0 = no limit).
        log_content: Per-field override. None → fall back to global LOG_AGENT_CONTENT.
    """
    should_log = log_content if log_content is not None else _LOG_CONTENT
    if not should_log:
        return _REDACTED
    limit = max_len if max_len is not None else _LOG_MAX_CHARS
    if limit <= 0:
        return text
    return _truncate(text, limit)


def _should_log_input(agent_name: str | None = None) -> bool:
    """Resolve input-logging flag: per-agent config → global env var."""
    if agent_name and agent_name in _AGENT_LOG_OVERRIDES:
        return _AGENT_LOG_OVERRIDES[agent_name]["log_input"]
    return _LOG_CONTENT


def _should_log_output(agent_name: str | None = None) -> bool:
    """Resolve output-logging flag: per-agent config → global env var."""
    if agent_name and agent_name in _AGENT_LOG_OVERRIDES:
        return _AGENT_LOG_OVERRIDES[agent_name]["log_output"]
    return _LOG_CONTENT


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... ({len(text)} chars)"


def _safe_summary(props: dict) -> str:
    """One-line summary for local logging."""
    parts = []
    for k, v in props.items():
        if k in ("xcv", "EventName", "Service"):
            continue
        sv = str(v)
        if len(sv) > 100:
            sv = sv[:100] + "..."
        parts.append(f"{k}={sv}")
    return ", ".join(parts)
