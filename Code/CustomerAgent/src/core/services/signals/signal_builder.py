"""SignalBuilder – deterministic signal detection pipeline.

Periodically calls MCP collection tools, evaluates activation rules
against returned data, computes signal strengths, evaluates compound
signals, and decides whether to invoke the GroupChat.

This is NOT an LLM agent — all logic is programmatic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .sources.kusto_signal_source import KustoSignalSource
from .signal_models import (
    ActivatedSignal,
    CompoundSignalResult,
    SignalBuilderResult,
    TypeSignalResult,
    evaluate_strength,
    normalize_strength,
)
from helper.agent_logger import AgentLogger, get_current_xcv, set_current_xcv, generate_xcv

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config"))


# ── Config loaders ────────────────────────────────────────────────

def _load_json(filename: str) -> dict[str, Any]:
    path = os.path.join(_CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_signal_template() -> dict[str, Any]:
    return _load_json("signals/signal_template.json")


def load_monitoring_context() -> dict[str, Any]:
    return _load_json("monitoring_context.json")


# ── MCP tool caller ──────────────────────────────────────────────

async def _call_collection_tool(
    tool_name: str,
    params: dict[str, str],
    service_name: str = "",
) -> list[dict[str, Any]]:
    """Call an MCP collection tool and return parsed rows.

    Delegates to KustoSignalSource for the actual MCP call, while
    preserving telemetry logging via AgentLogger.
    """
    import time as _time
    source = KustoSignalSource(
        tool_name=tool_name,
        params={},
        field_mappings={},
        source_type="kusto",
        signal_type="collection",
    )
    t0 = _time.monotonic()
    try:
        rows = await source.fetch_signals(params)
        elapsed = round((_time.monotonic() - t0) * 1000, 1)
        xcv = get_current_xcv()
        if xcv:
            AgentLogger.get_instance().log_mcp_collection_call(
                xcv=xcv, tool_name=tool_name, parameters=params,
                row_count=len(rows), duration_ms=elapsed,
                service_name=service_name,
            )
        return rows
    except Exception:
        logger.exception("Failed to call tool %s", tool_name)
        elapsed = round((_time.monotonic() - t0) * 1000, 1)
        xcv = get_current_xcv()
        if xcv:
            AgentLogger.get_instance().log_mcp_collection_call(
                xcv=xcv, tool_name=tool_name, parameters=params,
                row_count=0, duration_ms=elapsed, error="exception",
                service_name=service_name,
            )
        return []


# ── Data-field normaliser ─────────────────────────────────────────

def _snake_case(name: str) -> str:
    """Convert PascalCase / camelCase to snake_case."""
    import re
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with snake_case keys + original keys."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        out[k] = v
        sk = _snake_case(k)
        if sk != k:
            out[sk] = v
    return out


# ── Activation-rule evaluator ─────────────────────────────────────

def _check_activation(
    rules: list[dict[str, Any]],
    row_or_group: dict[str, Any],
) -> bool:
    """Evaluate activation_rules against a row or group aggregate.

    Rule key patterns:
      {field}_min: N       → value >= N
      {field}: true/false  → value == bool
      {field}_present: true → value is truthy and non-empty
      (compound) min_types_with_data: N → handled separately
    """
    for rule in rules:
        for key, threshold in rule.items():
            if key == "min_types_with_data":
                continue  # compound-level, not row-level

            if key.endswith("_min"):
                field_name = key[: -len("_min")]
                val = row_or_group.get(field_name, 0)
                try:
                    if float(val) < float(threshold):
                        return False
                except (TypeError, ValueError):
                    return False

            elif key.endswith("_present"):
                field_name = key[: -len("_present")]
                val = row_or_group.get(field_name)
                if not val or (isinstance(val, str) and not val.strip()):
                    return False

            elif key.endswith("_or_severity_increased"):
                # Special: is_escalated == True OR severity > initial_severity
                is_esc = row_or_group.get("is_escalated", False)
                sev = row_or_group.get("severity", "")
                init_sev = row_or_group.get("initial_severity", "")
                if not (is_esc is True or str(is_esc).lower() == "true"):
                    # Check severity increase (A > B > C, so string compare is reversed)
                    if not (sev and init_sev and sev < init_sev):
                        return False

            elif isinstance(threshold, bool):
                val = row_or_group.get(key, False)
                bool_val = val is True or str(val).lower() == "true"
                if bool_val != threshold:
                    return False

            else:
                # Direct equality
                val = row_or_group.get(key)
                if val != threshold:
                    return False

    return True


# ── Grouping + aggregation ────────────────────────────────────────

def _compute_groups(
    rows: list[dict[str, Any]],
    granularity_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Group rows by group_by keys and compute aggregates.

    If no explicit aggregates are defined, each row is its own group.
    """
    group_by = granularity_cfg.get("group_by", [])
    aggregates_cfg = granularity_cfg.get("aggregates")

    if not aggregates_cfg:
        # Per-row evaluation (e.g. subscription_region, single_case)
        return rows

    # Group rows
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = tuple(row.get(k, row.get(_snake_case(k))) for k in group_by)
        groups[key].append(row)

    results = []
    for _key, group_rows in groups.items():
        group_record: dict[str, Any] = {}
        # Carry forward group_by values from first row
        for k in group_by:
            group_record[k] = group_rows[0].get(k, group_rows[0].get(_snake_case(k)))
            group_record[_snake_case(k)] = group_record[k]

        # Compute aggregates
        for agg_name, agg_expr in aggregates_cfg.items():
            group_record[agg_name] = _compute_aggregate(agg_expr, group_rows)

        # Also store raw row count
        group_record["_row_count"] = len(group_rows)
        group_record["_rows"] = group_rows
        results.append(group_record)

    return results


def _compute_aggregate(expr: str, rows: list[dict[str, Any]]) -> Any:
    """Compute aggregate value from expression like count_distinct(Region)."""
    if expr.startswith("count_distinct("):
        field = expr[len("count_distinct("):-1]
        return len({r.get(field, r.get(_snake_case(field))) for r in rows})
    elif expr.startswith("count("):
        return len(rows)
    elif expr.startswith("sum("):
        field = expr[len("sum("):-1]
        return sum(float(r.get(field, r.get(_snake_case(field), 0)) or 0) for r in rows)
    elif expr.startswith("avg("):
        field = expr[len("avg("):-1]
        vals = [float(r.get(field, r.get(_snake_case(field), 0)) or 0) for r in rows]
        return sum(vals) / len(vals) if vals else 0
    elif expr.startswith("min("):
        field = expr[len("min("):-1]
        vals = [r.get(field, r.get(_snake_case(field))) for r in rows if r.get(field, r.get(_snake_case(field))) is not None]
        return min(vals) if vals else None
    elif expr.startswith("max("):
        field = expr[len("max("):-1]
        vals = [r.get(field, r.get(_snake_case(field))) for r in rows if r.get(field, r.get(_snake_case(field))) is not None]
        return max(vals) if vals else None
    return 0


# ── Per-type evaluation ──────────────────────────────────────────

def _build_activation_summary(
    granularity: str,
    group: dict[str, Any],
) -> str:
    """Build a human-readable summary of what activated."""
    parts = [f"granularity={granularity}"]
    # Include relevant aggregate fields
    for k, v in group.items():
        if k.startswith("_") or k in ("_rows", "_row_count"):
            continue
        if isinstance(v, (int, float)) and k.startswith("distinct"):
            parts.append(f"{k}={v}")
        elif isinstance(v, (int, float)) and "impacted" in k.lower():
            parts.append(f"{k}={v}")
        elif isinstance(v, (int, float)) and "count" in k.lower():
            parts.append(f"{k}={v}")
    return "; ".join(parts)


async def _evaluate_dependency_signal_type(
    sig_type: dict[str, Any],
    context: dict[str, Any],
) -> TypeSignalResult:
    """Evaluate SIG-TYPE-4: dependency service degradation via dependency_scan strategy.

    Flow:
    1. Call region tool to discover customer regions
    2. Load dependency_services.json for dependency service_tree_ids
    3. For each dependency, call multicustomer tool
    4. Filter results to customer regions only
    5. Enrich rows with DependencyServiceName
    6. Evaluate granularities as usual
    """
    type_id = sig_type["id"]
    type_name = sig_type["name"]

    # Step 1: Get customer regions
    region_cfg = sig_type["region_tool"]
    region_params = {}
    for param_name, context_key in region_cfg.get("parameters_from_context", {}).items():
        val = context.get(context_key, "")
        if val:
            region_params[param_name] = val

    region_rows = await _call_collection_tool(region_cfg["tool_name"], region_params, service_name=context.get("service_name", ""))
    customer_regions: set[str] = set()
    for row in region_rows:
        norm = _normalise_row(row)
        region = norm.get("region", norm.get("Region", ""))
        if region:
            customer_regions.add(region.lower())

    if not customer_regions:
        logger.info("SIG-TYPE-4: No customer regions found — skipping dependency scan")
        return TypeSignalResult(
            signal_type_id=type_id,
            signal_name=type_name,
            has_data=False,
            row_count=0,
            activated_signals=[],
            max_strength=0.0,
            best_confidence="Low",
        )

    logger.info("SIG-TYPE-4: Customer regions discovered: %s", customer_regions)

    # Step 2: Load dependency mappings → resolve dep files for this primary service
    dep_mappings = _load_json("dependency_services/dependency_mappings.json")
    primary_stid = context.get("service_tree_id", "")
    mappings = dep_mappings.get("mappings", {})

    if primary_stid not in mappings:
        logger.info(
            "SIG-TYPE-4: No dependency mapping for primary service_tree_id=%s — skipping",
            primary_stid,
        )
        return TypeSignalResult(
            signal_type_id=type_id,
            signal_name=type_name,
            has_data=False,
            row_count=0,
            activated_signals=[],
            max_strength=0.0,
            best_confidence="Low",
        )

    dep_keys = mappings[primary_stid].get("dependencies", [])
    dep_services: list[dict[str, Any]] = []
    dep_services_dir = os.path.join(_CONFIG_DIR, "dependency_services")
    for dep_key in dep_keys:
        dep_file = os.path.join(dep_services_dir, f"{dep_key}.json")
        if not os.path.isfile(dep_file):
            logger.warning("Dependency file not found: %s — skipping", dep_file)
            continue
        with open(dep_file, "r", encoding="utf-8") as f:
            dep_services.append(json.load(f))

    # Step 3: Call multicustomer tool for each dependency
    dep_tool_cfg = sig_type["dependency_tool"]
    dep_tool_name = dep_tool_cfg["tool_name"]
    dep_param_field = dep_tool_cfg["parameter_field"]

    all_rows: list[dict[str, Any]] = []
    for dep_svc in dep_services:
        dep_name = dep_svc["name"]
        dep_stid = dep_svc.get("service_tree_id", "")
        if not dep_stid or dep_stid.startswith("<TBD"):
            logger.debug("Skipping dependency '%s' — no service_tree_id configured", dep_name)
            continue

        rows = await _call_collection_tool(dep_tool_name, {dep_param_field: dep_stid}, service_name=dep_name)

        # Step 4: Filter to customer regions and enrich with dependency name
        for row in rows:
            norm = _normalise_row(row)
            row_region = (norm.get("region", norm.get("Region", "")) or "").lower()
            if row_region in customer_regions:
                norm["DependencyServiceName"] = dep_name
                norm["dependency_service_name"] = dep_name
                all_rows.append(norm)

    has_data = len(all_rows) > 0
    activated: list[ActivatedSignal] = []

    # Step 5: Evaluate granularities (same logic as standard path)
    for gran_cfg in sig_type.get("granularities", []):
        gran_name = gran_cfg["granularity"]

        if not all_rows:
            continue

        groups = _compute_groups(all_rows, gran_cfg)

        for group in groups:
            if not _check_activation(gran_cfg.get("activation_rules", []), group):
                continue

            try:
                raw_strength = evaluate_strength(gran_cfg["strength_formula"], group)
            except ValueError:
                logger.warning(
                    "Strength formula failed for %s/%s, defaulting to 1.0",
                    type_id, gran_name, exc_info=True,
                )
                raw_strength = 1.0

            max_raw = gran_cfg.get("max_raw_strength", raw_strength)
            strength = normalize_strength(raw_strength, max_raw)

            summary = _build_activation_summary(gran_name, group)
            matched = group.get("_rows", [group])

            activated.append(ActivatedSignal(
                signal_type_id=type_id,
                signal_name=type_name,
                granularity=gran_name,
                confidence=gran_cfg.get("confidence", "Medium"),
                strength=strength,
                raw_strength=raw_strength,
                activation_summary=summary,
                matched_rows=matched,
            ))

    max_strength = max((s.strength for s in activated), default=0.0)
    raw_max_strength = max((s.raw_strength for s in activated), default=0.0)
    best_confidence = "Low"
    if activated:
        confidence_order = ["Low", "Medium", "Medium-High", "High", "Highest"]
        best_confidence = max(
            (s.confidence for s in activated),
            key=lambda c: confidence_order.index(c) if c in confidence_order else 0,
        )

    return TypeSignalResult(
        signal_type_id=type_id,
        signal_name=type_name,
        has_data=has_data,
        row_count=len(all_rows),
        activated_signals=activated,
        max_strength=max_strength,
        raw_max_strength=raw_max_strength,
        best_confidence=best_confidence,
    )


async def _evaluate_signal_type(
    sig_type: dict[str, Any],
    context: dict[str, Any],
) -> TypeSignalResult:
    """Evaluate all granularities for one signal type."""
    type_id = sig_type["id"]
    type_name = sig_type["name"]
    collection_tools = sig_type.get("collection_tools", [])

    # Collect data from all collection tools for this type
    all_rows: list[dict[str, Any]] = []
    # Track which granularities are fed by which tool call
    granularity_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for tool_cfg in collection_tools:
        tool_name = tool_cfg["tool_name"]
        # Resolve parameters from monitoring context
        params = {}
        for param_name, context_key in tool_cfg.get("parameters_from_context", {}).items():
            val = context.get(context_key, "")
            if val:
                params[param_name] = val

        rows = await _call_collection_tool(tool_name, params, service_name=context.get("service_name", ""))
        normalised = [_normalise_row(r) for r in rows]

        for gran_name in tool_cfg.get("feeds_granularities", []):
            granularity_rows[gran_name].extend(normalised)

        all_rows.extend(normalised)

    has_data = len(all_rows) > 0
    activated: list[ActivatedSignal] = []

    # Evaluate each granularity
    for gran_cfg in sig_type.get("granularities", []):
        gran_name = gran_cfg["granularity"]
        rows_for_gran = granularity_rows.get(gran_name, all_rows)

        if not rows_for_gran:
            continue

        # Group and aggregate
        groups = _compute_groups(rows_for_gran, gran_cfg)

        for group in groups:
            if not _check_activation(gran_cfg.get("activation_rules", []), group):
                continue

            # Activation passed — compute strength
            try:
                raw_strength = evaluate_strength(gran_cfg["strength_formula"], group)
            except ValueError:
                logger.warning(
                    "Strength formula failed for %s/%s, defaulting to 1.0",
                    type_id, gran_name, exc_info=True,
                )
                raw_strength = 1.0

            max_raw = gran_cfg.get("max_raw_strength", raw_strength)
            strength = normalize_strength(raw_strength, max_raw)

            summary = _build_activation_summary(gran_name, group)
            matched = group.get("_rows", [group])

            activated.append(ActivatedSignal(
                signal_type_id=type_id,
                signal_name=type_name,
                granularity=gran_name,
                confidence=gran_cfg.get("confidence", "Medium"),
                strength=strength,
                raw_strength=raw_strength,
                activation_summary=summary,
                matched_rows=matched,
            ))

    # Determine type-level max strength and best confidence
    max_strength = max((s.strength for s in activated), default=0.0)
    raw_max_strength = max((s.raw_strength for s in activated), default=0.0)
    best_confidence = "Low"
    if activated:
        confidence_order = ["Low", "Medium", "Medium-High", "High", "Highest"]
        best_confidence = max(
            (s.confidence for s in activated),
            key=lambda c: confidence_order.index(c) if c in confidence_order else 0,
        )

    return TypeSignalResult(
        signal_type_id=type_id,
        signal_name=type_name,
        has_data=has_data,
        row_count=len(all_rows),
        activated_signals=activated,
        max_strength=max_strength,
        raw_max_strength=raw_max_strength,
        best_confidence=best_confidence,
    )


# ── Compound evaluation ──────────────────────────────────────────

def _evaluate_compounds(
    compound_cfgs: list[dict[str, Any]],
    type_results: dict[str, TypeSignalResult],
) -> list[CompoundSignalResult]:
    """Evaluate compound signal rules against type-level results."""
    results = []

    for cfg in compound_cfgs:
        required_types = cfg["required_signal_types"]
        rules = cfg.get("activation_rules", [])
        multiplier = cfg.get("correlation_multiplier", 1.5)

        # How many required types have data?
        types_with_data = [
            tid for tid in required_types
            if tid in type_results and type_results[tid].has_data
        ]

        # Check compound activation
        min_needed = 2  # default
        for rule in rules:
            if "min_types_with_data" in rule:
                min_needed = rule["min_types_with_data"]

        activated = len(types_with_data) >= min_needed

        # Compute compound strength: avg of contributing type strengths × multiplier, capped at 5.0
        raw_strength = 0.0
        strength = 0.0
        if activated:
            avg_strength = sum(
                type_results[tid].max_strength
                for tid in types_with_data
            ) / len(types_with_data)
            raw_strength = avg_strength * multiplier
            strength = min(raw_strength, 5.0)

        results.append(CompoundSignalResult(
            compound_id=cfg["id"],
            compound_name=cfg["name"],
            activated=activated,
            confidence=cfg.get("confidence", "Medium-High"),
            strength=strength,
            raw_strength=raw_strength,
            contributing_types=types_with_data,
            rationale=cfg.get("rationale", ""),
        ))

    return results


# ── Main evaluation entry point ──────────────────────────────────

async def _evaluate_for_context(
    template: dict[str, Any],
    context: dict[str, Any],
) -> SignalBuilderResult:
    """Run one evaluation cycle for a single customer + service_tree_id pair."""

    # Evaluate each signal type
    type_results_list: list[TypeSignalResult] = []
    for sig_type in template.get("signal_types", []):
        if sig_type.get("collection_strategy") == "dependency_scan":
            result = await _evaluate_dependency_signal_type(sig_type, context)
        else:
            result = await _evaluate_signal_type(sig_type, context)
        type_results_list.append(result)
        logger.info(
            "Signal type %s [%s/%s]: has_data=%s, activated=%d, max_strength=%.2f",
            result.signal_type_id,
            context.get("customer_name", "?"),
            context.get("service_tree_id", "?"),
            result.has_data,
            len(result.activated_signals), result.max_strength,
        )
        xcv = get_current_xcv()
        if xcv:
            # Extract distinct SLI names from activated signals' matched rows
            sli_names: set[str] = set()
            for sig in result.activated_signals:
                for row in sig.matched_rows:
                    sli = row.get("slo_sli_id") or row.get("SLO_SliId") or ""
                    if sli:
                        sli_names.add(sli)

            AgentLogger.get_instance().log_signal_type_evaluated(
                xcv=xcv,
                signal_type_id=result.signal_type_id,
                signal_name=result.signal_name,
                has_data=result.has_data,
                row_count=result.row_count,
                activated_count=len(result.activated_signals),
                max_strength=result.max_strength,
                best_confidence=result.best_confidence,
                activated_slis=sorted(sli_names),
            )

    type_results_map = {tr.signal_type_id: tr for tr in type_results_list}

    # Evaluate compound signals
    compound_cfgs = template.get("compound_signals", [])
    compound_results = _evaluate_compounds(compound_cfgs, type_results_map)

    for cr in compound_results:
        xcv = get_current_xcv()
        if xcv:
            AgentLogger.get_instance().log_compound_evaluated(
                xcv=xcv,
                compound_id=cr.compound_id,
                compound_name=cr.compound_name,
                activated=cr.activated,
                strength=cr.strength,
                contributing_types=cr.contributing_types,
                confidence=cr.confidence,
                rationale=cr.rationale,
            )
        if cr.activated:
            logger.info(
                "Compound %s activated: strength=%.2f, types=%s",
                cr.compound_id, cr.strength, cr.contributing_types,
            )

    # Decide action
    thresholds = template.get("decision_thresholds", {})
    strong_min = thresholds.get("strong_individual_signal_min_strength", 2.5)

    has_strong_individual = any(
        tr.max_strength >= strong_min for tr in type_results_list
    )
    has_compound = any(cr.activated for cr in compound_results)

    if has_strong_individual or has_compound:
        action = "invoke_group_chat"
    elif any(tr.activated_signals for tr in type_results_list):
        action = "watchlist"
    else:
        action = "quiet"

    logger.info(
        "SignalBuilder decision for %s/%s: %s",
        context.get("customer_name", "?"),
        context.get("service_tree_id", "?"),
        action,
    )
    xcv = get_current_xcv()
    if xcv:
        all_activated = [s for tr in type_results_list for s in tr.activated_signals]
        activated_compounds = [c for c in compound_results if c.activated]
        AgentLogger.get_instance().log_signal_decision(
            xcv=xcv,
            customer_name=context.get("customer_name", ""),
            service_tree_id=context.get("service_tree_id", ""),
            action=action,
            signal_count=len(all_activated),
            compound_count=len(activated_compounds),
        )

    return SignalBuilderResult(
        type_results=type_results_list,
        compound_results=compound_results,
        action=action,
        customer_name=context.get("customer_name", ""),
        service_tree_id=context.get("service_tree_id", ""),
        service_name=context.get("service_name", ""),
        xcv=get_current_xcv() or "",
    )


async def evaluate_signals(
    template: dict[str, Any] | None = None,
    monitoring_context: dict[str, Any] | None = None,
) -> list[SignalBuilderResult]:
    """Run one poll cycle across all monitoring targets.

    Args:
        template: Parsed signal_template.json.  Loaded from disk if None.
        monitoring_context: Parsed monitoring_context.json.  Loaded from disk if None.

    Returns:
        A list of SignalBuilderResult — one per customer × service_tree_id.
    """
    if template is None:
        template = load_signal_template()
    if monitoring_context is None:
        monitoring_context = load_monitoring_context()

    results: list[SignalBuilderResult] = []

    lookback_hours = monitoring_context.get("lookback_hours", "4h")

    for target in monitoring_context.get("targets", []):
        customer_name = target["customer_name"]
        service_tree_ids = target.get("service_tree_ids", [])

        contexts = []
        if not service_tree_ids:
            contexts.append({"customer_name": customer_name, "service_tree_id": "", "service_name": "", "lookback_hours": lookback_hours, "support_product_names": "[]", "owning_tenant_names": "[]"})
        else:
            for entry in service_tree_ids:
                # Support both {id, name} objects and plain string IDs
                if isinstance(entry, dict):
                    sid = entry["id"]
                    sname = entry.get("name", "")
                else:
                    sid = entry
                    sname = ""
                support_products = entry.get("support_product_names", [])
                owning_tenants = entry.get("owning_tenant_names", [])
                contexts.append({"customer_name": customer_name, "service_tree_id": sid, "service_name": sname, "lookback_hours": lookback_hours, "support_product_names": json.dumps(support_products), "owning_tenant_names": json.dumps(owning_tenants)})

        for ctx in contexts:
            # Reuse the parent XCV if one was already set (e.g. by app.py
            # /api/run endpoint) so that all events — signal evaluation,
            # investigation, tool calls — share the same correlation ID.
            # Only generate a new XCV when running standalone (CLI).
            parent_xcv = get_current_xcv()
            xcv = parent_xcv or generate_xcv()
            set_current_xcv(xcv)
            tracker = AgentLogger.get_instance()
            tracker.log_signal_evaluation_start(
                xcv=xcv,
                customer_name=ctx["customer_name"],
                service_tree_id=ctx["service_tree_id"],
                service_name=ctx.get("service_name", ""),
            )
            results.append(await _evaluate_for_context(template, ctx))

    return results


# ── Parallel investigation runner ────────────────────────────────

async def _run_investigations(
    results: list[SignalBuilderResult],
    on_group_chat: Any,
    max_concurrent: int = 5,
) -> None:
    """Run investigations in parallel with bounded concurrency.

    Each investigation gets its own XCV and runs inside a semaphore-guarded
    asyncio Task.  Failures in one investigation do not affect others.

    Args:
        results: All signal builder results (filtered to actionable here).
        on_group_chat: Async callback that receives a SignalBuilderResult.
        max_concurrent: Maximum number of concurrent investigations.
    """
    actionable = [r for r in results if r.action == "invoke_group_chat"]
    if not actionable:
        return

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _guarded(result: SignalBuilderResult) -> None:
        xcv = generate_xcv()
        set_current_xcv(xcv)
        async with semaphore:
            logger.info(
                "Invoking GroupChat for %s/%s (xcv=%s, %d signals, %d compounds)",
                result.customer_name, result.service_tree_id, xcv,
                len(result.all_activated_signals),
                len(result.activated_compounds),
            )
            try:
                await on_group_chat(result)
            except Exception:
                logger.exception(
                    "Investigation failed for %s/%s (xcv=%s)",
                    result.customer_name, result.service_tree_id, xcv,
                )

    logger.info(
        "Launching %d investigations (max_concurrent=%d)",
        len(actionable), max_concurrent,
    )

    async with asyncio.TaskGroup() as tg:
        for result in actionable:
            tg.create_task(_guarded(result))


# ── Timer loop ───────────────────────────────────────────────────

async def run_signal_builder_loop(
    on_group_chat: Any = None,
    poll_override_seconds: int | None = None,
):
    """Run SignalBuilder on a timer loop.

    Args:
        on_group_chat: Async callback invoked per target whose action == "invoke_group_chat".
            Receives the SignalBuilderResult as argument.
        poll_override_seconds: Override poll interval (for testing).
    """
    monitoring_ctx = load_monitoring_context()
    interval = poll_override_seconds or monitoring_ctx.get("poll_interval_minutes", 10) * 60
    max_concurrent = monitoring_ctx.get("max_concurrent_investigations", 5)

    logger.info("SignalBuilder loop starting (interval=%ds, targets=%d, max_concurrent=%d)",
                interval, len(monitoring_ctx.get("targets", [])), max_concurrent)

    while True:
        try:
            results = await evaluate_signals(monitoring_context=monitoring_ctx)

            if on_group_chat is not None:
                await _run_investigations(results, on_group_chat, max_concurrent)

        except Exception:
            logger.exception("SignalBuilder poll cycle failed")

        await asyncio.sleep(interval)
