"""Symptom template config loader.

Loads symptom template definitions from config/symptoms/*.json for use as
reference material by the triage agent (LLM-based symptom matching).

Hybrid model flow:
  Signals + Symptom Configs â†’ [Triage Agent / LLM] â†’ Confirmed Symptoms
                            â†’ [HypothesisScorer / programmatic] â†’ Ranked Hypotheses
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from helper.agent_logger import AgentLogger, get_current_xcv

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config"))
_SYMPTOM_DIR = os.path.join(_CONFIG_DIR, "symptoms")


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_symptom_templates() -> list[dict[str, Any]]:
    """Load all symptom templates from config/symptoms/*.json."""
    templates: list[dict[str, Any]] = []
    if not os.path.isdir(_SYMPTOM_DIR):
        logger.warning("Symptom config directory not found: %s", _SYMPTOM_DIR)
        return templates
    for filename in os.listdir(_SYMPTOM_DIR):
        if not filename.endswith(".json"):
            continue
        data = _load_json(os.path.join(_SYMPTOM_DIR, filename))
        for t in data.get("templates", []):
            t["_source_file"] = filename
            templates.append(t)
    # Log templates loaded
    xcv = get_current_xcv()
    if xcv:
        AgentLogger.get_instance().log_symptom_templates_loaded(
            xcv=xcv,
            template_count=len(templates),
            template_ids=[t.get("id", "") for t in templates],
        )
    return templates


def format_templates_for_prompt(templates: list[dict[str, Any]]) -> str:
    """Format symptom templates as structured reference material for the triage prompt.

    Strips internal keys (_source_file) and presents templates in a readable format
    the LLM can use to match signals to symptoms.
    """
    lines: list[str] = []
    for tmpl in templates:
        tid = tmpl["id"]
        name = tmpl.get("name", "")
        weight = tmpl.get("weight", 1)
        sources = ", ".join(tmpl.get("signal_sources", []))
        extracted = tmpl.get("extracted_when", "")
        filters = {k: v for k, v in tmpl.get("filters", {}).items() if k != "severity_rules"}
        sev_rules = tmpl.get("filters", {}).get("severity_rules", {})
        llm_fields = tmpl.get("fields", {}).get("llm_derived", [])

        lines.append(f"  {tid}: {name}")
        lines.append(f"    signal_sources: [{sources}]")
        lines.append(f"    weight: {weight}")
        lines.append(f"    when: {extracted}")
        if filters:
            lines.append(f"    criteria: {json.dumps(filters)}")
        if sev_rules:
            lines.append(f"    severity_rules: {json.dumps(sev_rules)}")
        if llm_fields:
            lines.append(f"    llm_derived_fields: {llm_fields}")
        lines.append("")
    return "\n".join(lines)
