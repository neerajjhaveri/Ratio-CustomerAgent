"""
Prompt loader for MAF GroupChat agents.

Loads agent instruction prompts from local text files in the prompts/ directory.
Optionally appends shared knowledge documents from the knowledge/ directory.
"""
from __future__ import annotations

import json
import logging
import os

from helper.agent_logger import AgentLogger

logger = logging.getLogger(__name__)

_PROMPTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "prompts"))
_KNOWLEDGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "knowledge"))
_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config"))


def load_prompt(prompt_file: str) -> str:
    """Load a prompt text file from the prompts directory.

    Args:
        prompt_file: Filename (e.g., 'maf_orchestrator_prompt.txt').

    Returns:
        Prompt text content.

    Raises:
        FileNotFoundError: If prompt file doesn't exist.
    """
    path = os.path.join(_PROMPTS_DIR, prompt_file)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    logger.info("Loaded prompt '%s' (%d chars)", prompt_file, len(text))
    return text


def _load_knowledge(filenames: list[str]) -> str:
    """Load and concatenate knowledge files from the knowledge/ directory."""
    parts: list[str] = []
    for name in filenames:
        path = os.path.join(_KNOWLEDGE_DIR, name)
        if not os.path.isfile(path):
            logger.warning("Knowledge file not found: %s", path)
            continue
        with open(path, "r", encoding="utf-8") as f:
            parts.append(f.read().strip())
        logger.info("Loaded knowledge '%s'", name)
    return "\n\n".join(parts)


def _resolve_template_vars(prompt_text: str) -> str:
    """Replace known {{VARIABLE}} placeholders with loaded config data."""
    if "{{ACTION_CATALOG}}" in prompt_text:
        catalog_path = os.path.join(_CONFIG_DIR, "actions", "action_catalog.json")
        if os.path.isfile(catalog_path):
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            prompt_text = prompt_text.replace(
                "{{ACTION_CATALOG}}", json.dumps(catalog, indent=2)
            )
            logger.info("Injected ACTION_CATALOG (%d actions)", len(catalog.get("actions", [])))
        else:
            logger.warning("Action catalog not found: %s", catalog_path)

    if "{{VALID_HYPOTHESIS_IDS}}" in prompt_text:
        prompt_text = prompt_text.replace(
            "{{VALID_HYPOTHESIS_IDS}}", _load_valid_hypothesis_ids()
        )

    return prompt_text


def _load_valid_hypothesis_ids() -> str:
    """Load all hypothesis IDs from the hypothesis catalog JSON files.

    Scans config/hypotheses/*.json and builds a formatted list grouped by
    category. This keeps prompts in sync with the catalog automatically —
    no manual updates when hypotheses are added or removed.
    """
    hyp_dir = os.path.join(_CONFIG_DIR, "hypotheses")
    if not os.path.isdir(hyp_dir):
        logger.warning("Hypotheses directory not found: %s", hyp_dir)
        return "(hypothesis catalog not found)"

    by_category: dict[str, list[str]] = {}
    total = 0
    for filename in sorted(os.listdir(hyp_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(hyp_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            for hyp in data.get("hypotheses", []):
                hid = hyp.get("id", "")
                cat = hyp.get("category", "unknown")
                if hid:
                    by_category.setdefault(cat, []).append(hid)
                    total += 1
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load hypothesis file %s: %s", filename, exc)

    lines: list[str] = []
    for cat in sorted(by_category):
        ids = ", ".join(by_category[cat])
        lines.append(f"  {cat.upper():14s} {ids}")

    logger.info("Injected VALID_HYPOTHESIS_IDS (%d hypotheses from %s)",
                total, hyp_dir)
    return "\n".join(lines)
    return prompt_text


def load_all_prompts(agents_config: list[dict]) -> dict[str, str]:
    """Load prompts for all agents defined in config.

    Args:
        agents_config: List of agent dicts from agents_config.json.

    Returns:
        Dict mapping agent name → prompt text.
    """
    prompts: dict[str, str] = {}
    for agent_cfg in agents_config:
        name = agent_cfg["name"]
        prompt_file = agent_cfg.get("prompt_file", "")
        if prompt_file:
            prompt_text = load_prompt(prompt_file)
            prompt_text = _resolve_template_vars(prompt_text)
        else:
            logger.warning("Agent '%s' has no prompt_file configured", name)
            prompt_text = f"You are {name}."

        # Append shared guideline documents if configured
        knowledge_files = agent_cfg.get("knowledge", [])
        if knowledge_files:
            knowledge_text = _load_knowledge(knowledge_files)
            if knowledge_text:
                prompt_text = f"{prompt_text}\n\n{knowledge_text}"

        prompts[name] = prompt_text

        # Log prompt to Application Insights
        tracker = AgentLogger.get_instance()
        tracker.log_prompt_loaded(name, prompt_file or "(default)", prompt_text)

    # Flush startup events so PromptLoaded records reach App Insights immediately
    tracker.flush()

    return prompts
