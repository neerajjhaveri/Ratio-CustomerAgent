# RATIO Customer Agent — Technical Design Document

> **Proactive customer health monitoring and automated investigation pipeline**
> built on Microsoft Agent Framework (MAF).

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture at a Glance](#architecture-at-a-glance)
3. [End-to-End Pipeline Flow](#end-to-end-pipeline-flow)
4. [Stage 0 — Monitoring Context & Configuration](#stage-0--monitoring-context--configuration)
5. [Stage 1 — Signal Builder (Deterministic)](#stage-1--signal-builder-deterministic)
6. [Stage 2 — Triage Agent (LLM)](#stage-2--triage-agent-llm)
7. [Stage 3 — Hypothesis Scoring (Deterministic)](#stage-3--hypothesis-scoring-deterministic)
8. [Stage 4 — Investigation GroupChat (LLM Multi-Agent)](#stage-4--investigation-groupchat-llm-multi-agent)
9. [Stage 5 — Action Planning & Notification](#stage-5--action-planning--notification)
10. [Configuration-Driven Design](#configuration-driven-design)
11. [Agent Roster](#agent-roster)
12. [Middleware Stack](#middleware-stack)
13. [MCP Integration](#mcp-integration)
14. [Observability & Telemetry](#observability--telemetry)
15. [Entry Points](#entry-points)
16. [Project Structure](#project-structure)

---

## System Overview

The Customer Agent is a **hybrid AI pipeline** that combines deterministic signal
processing with LLM-powered multi-agent investigation to proactively detect,
diagnose, and act on customer health issues — before the customer notices.

**Key design principle:** Deterministic logic handles what can be computed
exactly (signal activation, hypothesis scoring); LLMs handle what requires
reasoning (symptom matching, evidence evaluation, root-cause determination).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RATIO Customer Agent                             │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │   Signal      │───▶│   Triage     │───▶│  Hypothesis Scoring     │  │
│  │   Builder     │    │   (LLM)      │    │  (Deterministic)        │  │
│  │(Deterministic)│    └──────────────┘    └────────────┬─────────────┘  │
│  └──────────────┘                                      │               │
│        ▲                                               ▼               │
│   MCP Tools                              ┌──────────────────────────┐  │
│   (Kusto)                                │  Investigation GroupChat │  │
│                                          │  (LLM Multi-Agent)       │  │
│                                          │  ┌──────┐ ┌──────────┐  │  │
│                                          │  │Planner│ │Collectors│  │  │
│                                          │  └──┬───┘ └────┬─────┘  │  │
│                                          │     │          │        │  │
│                                          │  ┌──▼──────────▼─────┐  │  │
│                                          │  │     Reasoner      │  │  │
│                                          │  └────────┬──────────┘  │  │
│                                          │           │             │  │
│                                          │  ┌────────▼──────────┐  │  │
│                                          │  │  Action Planner   │  │  │
│                                          │  └───────────────────┘  │  │
│                                          └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture at a Glance

```
                    ┌──────────────────────────────────────────────┐
                    │           Monitoring Context                  │
                    │  (customer, service_tree_id, lookback)       │
                    └────────────────────┬─────────────────────────┘
                                         │
                    ┌────────────────────▼─────────────────────────┐
                    │         SIGNAL BUILDER (Deterministic)        │
                    │                                               │
                    │  For each signal type:                        │
                    │    1. Call MCP collection tools (Kusto)       │
                    │    2. Normalize rows (PascalCase → snake_case)│
                    │    3. Group by granularity dimensions         │
                    │    4. Evaluate activation rules               │
                    │    5. Compute signal strength (formula)       │
                    │  Then:                                        │
                    │    6. Evaluate compound signals               │
                    │    7. Decision: quiet / watchlist / invoke    │
                    └────────────────────┬─────────────────────────┘
                                         │
                          action = "invoke_group_chat"
                                         │
                    ┌────────────────────▼─────────────────────────┐
                    │      INVESTIGATION PIPELINE (Hybrid)          │
                    │                                               │
                    │  Phase 1: TRIAGE ──────────────── (LLM)      │
                    │    ├─ Match signals → symptom templates       │
                    │    └─ Confirm symptoms, assign severity       │
                    │                                               │
                    │  Phase 2: HYPOTHESIZING ────── (Deterministic)│
                    │    ├─ Score hypotheses by symptom overlap     │
                    │    └─ Rank by match_score (weighted strength) │
                    │                                               │
                    │  Phase 3: PLANNING ────────────── (LLM)      │
                    │    └─ Map evidence_needed → collector agents  │
                    │                                               │
                    │  Phase 4: COLLECTING ─────────── (LLM+Tools) │
                    │    ├─ SLI Collector    → MCP tools            │
                    │    ├─ Incident Collector → MCP tools          │
                    │    └─ Support Collector → MCP tools           │
                    │                                               │
                    │  Phase 5: REASONING ──────────── (LLM)       │
                    │    ├─ Evaluate evidence vs hypothesis         │
                    │    └─ Verdict: CONFIRMED / CONTRIBUTING /     │
                    │       REFUTED / needs_more_evidence           │
                    │                                               │
                    │  Phase 6: ACTING ─────────────── (LLM)       │
                    │    └─ Select actions from Action Catalog      │
                    │                                               │
                    │  Phase 7: NOTIFYING ──────────── (LLM)       │
                    │    └─ investigation_resolved signal           │
                    └──────────────────────────────────────────────┘
```

---

## End-to-End Pipeline Flow

The complete pipeline is a **7-stage process** from raw telemetry data to
actionable remediation. This section walks through every stage with the
decision points and data transformations at each boundary.

```
┌────────────┐     ┌────────────┐     ┌──────────────┐     ┌───────────┐
│ Monitoring │────▶│  Signal    │────▶│  Triage      │────▶│ Hypothesis│
│ Context    │     │  Builder   │     │  Agent (LLM) │     │ Scorer    │
│            │     │            │     │              │     │           │
│ customer,  │     │ MCP calls, │     │ signals →    │     │ symptoms ×│
│ service,   │     │ activation │     │ symptoms     │     │ templates │
│ lookback   │     │ rules,     │     │              │     │ = ranked  │
│            │     │ strength   │     │              │     │ hypotheses│
└────────────┘     └──────┬─────┘     └──────────────┘     └─────┬─────┘
                          │                                       │
               ┌──────────▼──────────┐                           │
               │ Decision Gate       │                           │
               │                     │                           │
               │ invoke_group_chat ──┼───────────────────────────┘
               │ watchlist ──────────┼──▶ (log only, no investigation)
               │ quiet ──────────────┼──▶ (no action)
               └─────────────────────┘

         ┌───────────────────────────────────────────────────────────┐
         │              INVESTIGATION GROUPCHAT                       │
         │                                                           │
         │  ┌──────────────┐     ┌──────────────┐                   │
         │  │  Evidence     │────▶│  Collector   │──── MCP Tools    │
         │  │  Planner      │     │  Sub-Agents  │     (Kusto)      │
         │  └──────────────┘     └──────┬───────┘                   │
         │                              │                            │
         │                     ┌────────▼────────┐                   │
         │                     │    Reasoner     │                   │
         │                     │                 │                   │
         │                     │ CONFIRMED ──────┼──▶ Action Planner│
         │                     │ CONTRIBUTING ───┼──▶ Action Planner│
         │                     │ REFUTED ────────┼──▶ Next Hypothesis│
         │                     │ needs_more ─────┼──▶ Evidence Planner│
         │                     └─────────────────┘   (max 2 cycles) │
         └───────────────────────────────────────────────────────────┘
```

---

## Stage 0 — Monitoring Context & Configuration

Before any processing begins, the system loads its configuration from JSON
files that define **what to monitor**, **what signals to look for**, and
**what constitutes a problem**.

### Monitoring Context (`config/monitoring_context.json`)

Defines the monitoring targets — which customers and services to watch:

```json
{
  "poll_interval_minutes": 10,
  "max_concurrent_investigations": 5,
  "lookback_hours": "4h",
  "targets": [
    {
      "customer_name": "BlackRock, Inc",
      "service_tree_ids": [
        {
          "id": "49c39e84-...",
          "name": "ScaleSet Platform and Solution",
          "support_product_names": ["Azure Virtual Machine - Linux", ...],
          "owning_tenant_names": ["ScaleSet Platform and Solution", "WACAP"]
        }
      ]
    }
  ]
}
```

Each target generates an independent evaluation cycle. Multiple targets run
in parallel with bounded concurrency (`max_concurrent_investigations`).

### Configuration Hierarchy

```
config/
├── monitoring_context.json        ← WHO to monitor (customers, services)
├── agents/
│   └── agents_config.json         ← Agent definitions (names, models, tools, prompts)
├── signals/
│   └── signal_template.json       ← WHAT to detect (signal types, activation rules)
├── symptoms/
│   ├── sli_breach.json            ← Symptom templates for SLI signals
│   ├── outage_exposure.json       ← Symptom templates for outage signals
│   ├── support_tickets.json       ← Symptom templates for support signals
│   └── dependency_degradation.json← Symptom templates for dependency signals
├── hypotheses/
│   ├── sli_hypotheses.json        ← Hypothesis templates for SLI root causes
│   ├── outage_hypotheses.json     ← Hypothesis templates for outage root causes
│   ├── dependency_hypotheses.json ← Hypothesis templates for dependency failures
│   └── risk_hypotheses.json       ← Hypothesis templates for proactive risks
├── evidence/
│   └── evidence_requirements.json ← Evidence needed to confirm/refute hypotheses
├── actions/
│   └── action_catalog.json        ← Available remediation actions
└── dependency_services/
    ├── dependency_mappings.json   ← Primary → dependency service relationships
    ├── xstore.json                ← Dependency service definitions
    ├── azure_allocator.json
    └── ...
```

---

## Stage 1 — Signal Builder (Deterministic)

**File:** `src/core/signals/signal_builder.py`
**Nature:** Fully deterministic — no LLM involved.

The Signal Builder is a programmatic pipeline that polls telemetry data via
MCP tools, evaluates activation rules, and decides whether an investigation
is warranted. It runs either as a **one-shot** (`run_signal_builder.py`) or
on a **continuous timer** (`run_signal_builder_loop.py`).

### Signal Types

Each signal type represents a category of health degradation:

| Signal Type | Name | Data Source | What It Detects |
|-------------|------|-------------|-----------------|
| `SIG-TYPE-1` | SLI Breach Detected | SLI monitoring (Kusto) | Service Level Indicator violations |
| `SIG-TYPE-2` | Support Ticket Surge | Support cases (Kusto) | Abnormal support case patterns |
| `SIG-TYPE-3` | Outage/Incident Exposure | IcM incidents (Kusto) | Active outages affecting customer |
| `SIG-TYPE-4` | Dependency Service Degradation | Multi-service scan (Kusto) | Upstream dependency failures |

### Processing Pipeline Per Signal Type

```
┌────────────────────────────────────────────────────────────────────┐
│                    Per Signal Type Evaluation                       │
│                                                                    │
│  1. COLLECT DATA                                                   │
│     ├─ Call MCP collection tools with monitoring context params     │
│     ├─ Parse JSON response → rows                                  │
│     └─ Normalize field names (PascalCase → snake_case + original)  │
│                                                                    │
│  2. GROUP BY GRANULARITY                                           │
│     ├─ subscription_region: per-subscription + region              │
│     ├─ cross_region: same SLI across ≥2 regions                   │
│     ├─ cross_subscription: same SLI across ≥2 subscriptions       │
│     ├─ multi_sli: ≥2 distinct SLIs in same subscription + region  │
│     └─ (signal type 4): per-dependency service, filtered to       │
│        customer regions                                            │
│                                                                    │
│  3. EVALUATE ACTIVATION RULES                                      │
│     ├─ {field}_min: N       → value >= N                           │
│     ├─ {field}: true/false  → boolean match                        │
│     ├─ {field}_present: true → value is non-empty                  │
│     └─ Custom rules (e.g., escalation detection)                   │
│                                                                    │
│  4. COMPUTE RAW STRENGTH (per activated granularity)               │
│     └─ Formula evaluation with safe math:                          │
│        Example: impacted_resources × log2(1 + duration/5) ×       │
│                 (100 - avg_value) / 100                            │
│                                                                    │
│  5. NORMALIZE TO 0–5 SCALE                                        │
│     └─ strength = min(raw / max_raw_strength, 1.0) × 5.0          │
│        Activated signals get a floor of 0.5 (always registers)    │
│        max_raw_strength is defined per granularity in config       │
│                                                                    │
│  6. AGGREGATE                                                      │
│     ├─ max_strength across all granularities (now 0–5)             │
│     └─ best_confidence (Low → Medium → High → Highest)             │
└────────────────────────────────────────────────────────────────────┘
```

### Granularity System

Signals are evaluated at multiple **granularity levels** to detect patterns
at different scopes. Higher granularities carry higher confidence because
they indicate broader, more systemic issues:

```
                          Confidence
                              ▲
              Highest ────────┤  multi_customer_same_region_sli
                              │  (same SLI failing across multiple customers)
                              │
                 High ────────┤  cross_region, cross_subscription, multi_sli
                              │  (patterns across boundaries)
                              │
               Medium ────────┤  subscription_region
                              │  (single scope — could be noise)
                              │
                  Low ────────┤  (no activation)
                              └──────────────────────────────────▶ Scope
```

### Compound Signal Evaluation

After individual signal types are evaluated, **compound signals** detect
correlations across signal types (e.g., SLI breach + active outage):

```
┌──────────────────────────────────────────────────────────────┐
│                  Compound Signal Evaluation                    │
│                                                              │
│  Input: TypeSignalResult per signal type                     │
│                                                              │
│  Rule: "If ≥2 of [SIG-TYPE-1, SIG-TYPE-3, SIG-TYPE-4]      │
│          have data, activate compound signal"                │
│                                                              │
│  Strength = min(avg(type strengths) × multiplier, 5.0)       │
│                                                              │
│  Example:                                                    │
│    SIG-TYPE-1 (SLI breach) strength=3.8 (High)              │
│    SIG-TYPE-3 (outage)     strength=2.5 (Moderate)          │
│    Compound = min(avg(3.8, 2.5) × 1.5, 5.0)                │
│            = min(3.15 × 1.5, 5.0) = 4.7 (Critical)         │
└──────────────────────────────────────────────────────────────┘
```

### Decision Gate

The final decision is deterministic, based on threshold comparison:

```
                    ┌──────────────────────────┐
                    │     Decision Thresholds   │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
     ┌────────▼──────┐  ┌───────▼───────┐  ┌───────▼───────┐
     │ invoke_group_ │  │   watchlist   │  │     quiet     │
     │ chat          │  │              │  │               │
     │               │  │ Some signals │  │ No signals    │
     │ Strong signal │  │ activated    │  │ activated     │
     │ (≥ 2.5 on    │  │ but below   │  │               │
     │  0–5 scale)  │  │ 2.5         │  │               │
     │ OR compound   │  │              │  │               │
     │ activated     │  │              │  │               │
     └───────┬───────┘  └──────────────┘  └───────────────┘
             │
             ▼
    Trigger Investigation Pipeline
```

### Score Normalization (0–5 Scale)

All signal and hypothesis scores are normalized to a **unified 0–5 scale**,
providing consistent, human-interpretable severity across all pipeline stages.

#### Semantic Labels

| Score | Label | Meaning |
|-------|-------|--------|
| 0 | None | No signal detected |
| 1 | Low | Minimal impact, likely noise |
| 2 | Moderate | Noticeable impact, monitor closely |
| 3 | Significant | Clear issue, investigation warranted |
| 4 | High | Major impact, immediate attention needed |
| 5 | Critical | Severe, widespread impact |

#### How Normalization Works

```
┌──────────────────────────────────────────────────────────────────────┐
│                  Signal Strength Normalization                        │
│                                                                      │
│  Each granularity in signal_template.json defines a max_raw_strength │
│  representing the p95 expected raw value for that formula.           │
│                                                                      │
│  Formula:                                                            │
│    normalized = min(raw_strength / max_raw_strength, 1.0) × 5.0     │
│    if normalized > 0: normalized = max(normalized, 0.5)  ← floor    │
│                                                                      │
│  Examples:                                                           │
│    SLI breach (subscription_region): max_raw=30                      │
│      raw=15  → min(15/30, 1) × 5 = 2.5 (Moderate)                  │
│      raw=30  → min(30/30, 1) × 5 = 5.0 (Critical)                  │
│      raw=60  → min(60/30, 1) × 5 = 5.0 (Critical — capped)        │
│      raw=0.5 → min(0.5/30, 1) × 5 = 0.5 (Low — floored)           │
│                                                                      │
│    Support case (single_case): max_raw=9                             │
│      raw=3 (Sev A) → min(3/9, 1) × 5 = 1.7 (Moderate)             │
│      raw=9 (Sev A + CritSit) → 5.0 (Critical)                     │
│                                                                      │
│  Compound signals:                                                   │
│    strength = min(avg(contributing_type_strengths) × multiplier, 5)  │
│                                                                      │
│  Hypothesis scores:                                                  │
│    match_score = overlap_ratio (0–1) × agg_signal_strength (0–5)    │
│    Result: 0–5 automatically                                        │
└──────────────────────────────────────────────────────────────────────┘
```

#### `max_raw_strength` Reference

Defined per granularity in `config/signals/signal_template.json`:

| Signal Type | Granularity | max_raw_strength | Rationale |
|-------------|-------------|------------------|----------|
| SIG-TYPE-1 | subscription_region | 30 | ~10 resources × log2(13) × 80% |
| SIG-TYPE-1 | cross_region | 40 | 3 regions × 15 resources × 80% |
| SIG-TYPE-1 | cross_subscription | 40 | Same shape as cross_region |
| SIG-TYPE-1 | multi_sli | 40 | 4 SLIs × 10 resources |
| SIG-TYPE-1 | multi_customer_same_region_sli | 80 | 5 subs × 20 resources × 80% |
| SIG-TYPE-1 | multi_sli_region_wide | 200 | 3 SLIs × 5 subs × 20 resources |
| SIG-TYPE-2 | single_case | 9 | Sev A (3) × CritSit (3) |
| SIG-TYPE-2 | crit_sit | 9 | Same ceiling |
| SIG-TYPE-2 | escalated | 6 | Sev A (3) × 2 |
| SIG-TYPE-2 | multi_case_same_product | 15 | 5 cases × Sev A (3) |
| SIG-TYPE-2 | multi_customer_same_product | 40 | 3 custs × 5 cases × Sev factor |
| SIG-TYPE-3 | single_incident | 6 | (4−1) × 2 |
| SIG-TYPE-3 | outage_confirmed | 6 | (4−1) × 2 |
| SIG-TYPE-3 | with_child_incidents | 50 | 20 children × (4−1) |
| SIG-TYPE-3 | customer_correlated | 4.5 | (4−1) × 1.5 |
| SIG-TYPE-4 | dep_sli_breach_in_customer_region | 40 | 50 resources × 80% |
| SIG-TYPE-4 | multi_dep_sli_breach_in_region | 200 | Multi-dimensional product |
| SIG-TYPE-4 | multi_dep_service_breach_in_region | 100 | 3 deps × 4 SLIs × 10 subs |

#### Telemetry

Both `raw_strength` (original formula output) and `strength` (normalized 0–5)
are stored in every `ActivatedSignal` and `CompoundSignalResult` for
debugging and calibration. The `to_dict()` methods include both fields.

---

## Stage 2 — Triage Agent (LLM)

**File:** `src/core/investigation/investigation_runner.py` (orchestration) +
`src/prompts/investigation_triage_prompt.txt`
**Nature:** LLM-powered reasoning

When the Signal Builder triggers an investigation, the **Triage Agent** is
the first LLM agent to process the activated signals. Its job is to match
raw signal data against **symptom templates** and confirm which symptoms
are present.

### What the Triage Agent Receives

The task message sent to the GroupChat contains:

1. **Activated signals** — type, granularity, confidence, strength (0–5 with label), summary
2. **Activated compound signals** — cross-type correlations
3. **Signal data rows** — up to 5 raw data rows per signal (for filter evaluation)
4. **Symptom templates** — structured reference material from `config/symptoms/`

### Symptom Template Matching

Symptom templates define the conditions under which a symptom is "confirmed":

```
Symptom Template Example (SYM-SLI-002):
  ┌────────────────────────────────────────────────────────┐
  │  Name: Severe SLI Degradation                          │
  │  Source: SIG-TYPE-1                                    │
  │  Weight: 3 (high severity indicator)                   │
  │  Filters:                                              │
  │    max_min_value: 1.0                                  │
  │    severity_rules:                                     │
  │      CRITICAL: min_value == 0 AND avg_value < 1.0     │
  │      HIGH:     min_value == 0 OR  avg_value < 10.0    │
  │      WARNING:  avg_value < 50.0                        │
  │  LLM-derived fields: [severity]                        │
  └────────────────────────────────────────────────────────┘
```

The triage agent **reasons over the data rows** against each template:
- Evaluates filter criteria (min thresholds, value ranges)
- Computes LLM-derived fields (e.g., severity classification)
- Evaluates cross-source correlations (e.g., time overlap between incidents and SLI breaches)
- Assigns investigation category and severity

### Triage Output

```json
{
  "structured_output": {
    "symptoms": [
      {
        "template_id": "SYM-SLI-001",
        "status": "confirmed",
        "text": "SLI 'availability_sli' has 12 impacted resources...",
        "weight": 1,
        "signal_strength": 3.8,
        "severity": "HIGH"
      }
    ]
  },
  "signals": {
    "phase_complete": "triage"
  }
}
```

---

## Stage 3 — Hypothesis Scoring (Deterministic)

**File:** `src/core/investigation/hypothesis_scorer.py`
**Nature:** Fully deterministic — no LLM involved.

Immediately after triage completes (detected via `phase_complete: "triage"`),
the **hypothesis scorer** runs programmatically. This is Stage 2 of the
hybrid pipeline — it bridges LLM triage and LLM investigation.

### Scoring Formula

All hypothesis scores are on the **0–5 scale** (same as signal strengths).

```
match_score = overlap_ratio × agg_signal_strength

Where:
  overlap_ratio       = weighted_matched / weighted_total  (0.0 – 1.0)
  weighted_matched    = Σ weight(symptom) for each expected symptom that is confirmed
  weighted_total      = Σ weight(symptom) for ALL expected symptoms
  agg_signal_strength = aggregated signal_strength of matched symptoms (0–5, normalized)

Result: 0.0 – 5.0 (automatically bounded since overlap ≤ 1.0 and strength ≤ 5.0)
```

Hypothesis scores displayed to agents include the semantic label:
`score=3.2 (Significant)  status=active`

### How It Works

```
┌────────────────────────────────────────────────────────────────────┐
│                   Hypothesis Scoring Pipeline                       │
│                                                                    │
│  Input: Confirmed Symptoms from Triage Agent                       │
│         Hypothesis Templates from config/hypotheses/               │
│                                                                    │
│  For each hypothesis template:                                     │
│    1. Count overlap: expected_symptoms ∩ confirmed_symptoms        │
│    2. Check threshold: matched_count ≥ min_symptoms_for_match?     │
│    3. Compute weighted match_score (0–5 scale) using symptom       │
│       weights and normalized signal strengths                      │
│    4. Filter by min_score_threshold                                │
│                                                                    │
│  Output: Ranked list of qualifying hypotheses (highest score first)│
│         All scores on 0–5 scale with semantic labels               │
│                                                                    │
│  Example:                                                          │
│    HYP-SLI-001 (Outage Caused SLI Breach)                         │
│      expected: [SYM-SLI-001, SYM-SLI-002, SYM-OUT-001, ...]     │
│      matched:  [SYM-SLI-001, SYM-SLI-002, SYM-OUT-002]          │
│      matched_count = 3 ≥ min(3) ✓                                 │
│      match_score = 3.2 (Significant)                               │
│                                                                    │
│    HYP-SLI-004 (Dependency Failure)                                │
│      matched_count = 1 < min(2) ✗  → discarded                   │
└────────────────────────────────────────────────────────────────────┘
```

### Hypothesis Template Structure

Each hypothesis template in `config/hypotheses/` encodes domain knowledge:

| Field | Purpose | Example |
|-------|---------|---------|
| `id` | Unique identifier | `HYP-SLI-001` |
| `name` | Human-readable name | "Outage Caused SLI Breach" |
| `statement` | Parameterized description | "The SLI breach on '{slo_sli_id}'..." |
| `expected_symptoms` | Which symptoms support this hypothesis | `["SYM-SLI-001", "SYM-OUT-002"]` |
| `min_symptoms_for_match` | Minimum overlap to qualify | `3` |
| `evidence_needed` | What data to collect to verify | `["ER-OUT-001", "ER-SLI-001"]` |
| `supporting_signals` | Expert guidance for the reasoner | "Strongest when SYM-OUT-003 co-occurs..." |

---

## Stage 4 — Investigation GroupChat (LLM Multi-Agent)

**File:** `src/core/investigation/investigation_runner.py`
**Framework:** Microsoft Agent Framework `GroupChatBuilder`

Once hypotheses are scored and ranked, the investigation enters a **multi-agent
GroupChat** orchestrated by an LLM orchestrator that decides turn order.

### Investigation Phase Lifecycle

```
┌──────────┐   ┌────────┐   ┌──────────────┐   ┌──────────┐   ┌────────────┐
│INITIALIZ-│──▶│ TRIAGE │──▶│ HYPOTHESIZING│──▶│ PLANNING │──▶│ COLLECTING │
│ING       │   │        │   │              │   │          │   │            │
└──────────┘   └────────┘   └──────────────┘   └──────────┘   └─────┬──────┘
                                                                     │
     ┌───────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────┐   ┌────────┐   ┌──────────┐   ┌──────────┐
│REASONING │──▶│ ACTING │──▶│NOTIFYING │──▶│ COMPLETE │
│          │   │        │   │          │   │          │
└────┬─────┘   └────────┘   └──────────┘   └──────────┘
     │
     │  needs_more_evidence?  ──▶ Back to PLANNING (max 2 cycles)
     │  hypothesis_refuted?   ──▶ Next hypothesis in ranked order
     │
```

### Agent Interactions Within GroupChat

The investigation orchestrator decides which agent speaks next based on the
current phase and investigation state:

```
┌─────────────────────────────────────────────────────────────────────┐
│              Investigation GroupChat — Agent Flow                     │
│                                                                     │
│  Orchestrator (investigation_orchestrator)                           │
│    │                                                                │
│    ├──▶ triage_agent ─────────────────── Phase: TRIAGE             │
│    │      └─ Matches signals → symptoms                            │
│    │      └─ [Programmatic: HypothesisScorer runs after triage]    │
│    │                                                                │
│    ├──▶ evidence_planner ─────────────── Phase: PLANNING/COLLECTING│
│    │      ├─ Maps evidence_needed → collector agents               │
│    │      ├──▶ sli_collector ──── MCP: collect_impacted_resource_* │
│    │      ├──▶ incident_collector ── MCP: collect_incident_details  │
│    │      └──▶ support_collector ── MCP: collect_support_request   │
│    │                                                                │
│    ├──▶ reasoner ─────────────────────── Phase: REASONING          │
│    │      ├─ Evaluates evidence against hypothesis                 │
│    │      ├─ Per-symptom verdicts (satisfied/not_satisfied)        │
│    │      └─ Hypothesis verdict:                                   │
│    │           CONFIRMED → proceed to action_planner               │
│    │           CONTRIBUTING → proceed to action_planner            │
│    │           REFUTED → orchestrator cycles to next hypothesis    │
│    │           needs_more_evidence → back to evidence_planner      │
│    │                                                                │
│    └──▶ action_planner ──────────────── Phase: ACTING              │
│           └─ Selects actions from Action Catalog                   │
│           └─ Prioritizes by tier (auto/gated) and confidence       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Evidence Collection Architecture

The **Evidence Planner** is a coordinator agent with sub-agents. It dispatches
domain-specific collectors in parallel, each specialized for a data source:

```
┌──────────────────────────────────────────────────────────────────┐
│                    Evidence Collection                             │
│                                                                  │
│  Evidence Planner (agent_tools mode — calls sub-agents)          │
│    │                                                             │
│    ├──▶ SLI Collector                                           │
│    │      Tools: collect_impacted_resource_customer_tool          │
│    │             collect_impacted_resource_multicustomer_tool     │
│    │      Data:  Per-subscription SLI breach aggregates          │
│    │             Cross-customer impact patterns                  │
│    │                                                             │
│    ├──▶ Incident Collector                                      │
│    │      Tools: collect_incident_details_tool                   │
│    │      Data:  IcM incidents, severity, outage status          │
│    │             Impact timeline, child incident count           │
│    │                                                             │
│    └──▶ Support Collector                                       │
│           Tools: collect_support_request_tool                    │
│           Data:  Customer support cases, CritSits               │
│                  Escalation patterns, severity changes           │
│                                                                  │
│  Each collector:                                                 │
│    1. Calls MCP tools with investigation context parameters      │
│    2. Synthesizes raw data into evidence items                   │
│    3. Assigns preliminary verdicts (supports/refutes)            │
│    4. Returns structured evidence_items to evidence_planner      │
└──────────────────────────────────────────────────────────────────┘
```

### Hypothesis Evaluation Loop

The investigation supports **sequential hypothesis evaluation** and
**evidence cycling**:

```
Hypotheses ranked by score: [HYP-001 (3.2 Significant), HYP-002 (2.1 Moderate), HYP-003 (1.5 Low)]

Iteration 1: Evaluate HYP-001
  ├─ Evidence Planner collects ER-OUT-001, ER-SLI-001, ER-SLI-002
  ├─ Reasoner evaluates:
  │    SYM-SLI-001: satisfied ✓
  │    SYM-SLI-002: satisfied ✓
  │    SYM-OUT-002: not_satisfied ✗ (no matching outage found)
  │    Verdict: CONTRIBUTING (0.65 confidence)
  └─ → Proceed to Action Planner

  (If REFUTED instead):
  └─ → Orchestrator advances to HYP-002

  (If needs_more_evidence):
  └─ → Evidence Planner collects additional data (cycle 2 of max 2)
```

### Evidence Requirement Mapping

Evidence requirements (`config/evidence/evidence_requirements.json`) define
**what data** to collect and **which tools** to call:

| ER ID | Description | Tool | Category |
|-------|-------------|------|----------|
| `ER-OUT-001` | Recent high-severity IcM incidents | `collect_incident_details_tool` | IcM |
| `ER-SLI-001` | Customer-specific SLI breach data | `collect_impacted_resource_customer_tool` | SLI |
| `ER-SLI-002` | Multi-customer SLI impact | `collect_impacted_resource_multicustomer_tool` | SLI |
| `ER-TKT-001` | Customer support cases | `collect_support_request_tool` | Support |
| `ER-TKT-002` | Cross-customer support patterns | `collect_support_request_tool` | Support |
| `ER-DEP-002` | Dependency service SLI data | `collect_impacted_resource_multicustomer_tool` | Dependency |
| `ER-LOAD-001` | Workload spike detection | `collect_impacted_resource_customer_tool` | SLI |

---

## Stage 5 — Action Planning & Notification

**File:** `src/prompts/investigation_action_planner_prompt.txt`
**Nature:** LLM-powered selection from a deterministic catalog

The **Action Planner** selects remediation actions from a pre-defined
**Action Catalog** (`config/actions/action_catalog.json`) based on the
confirmed or contributing hypothesis.

### Action Catalog Structure

Actions are tiered by automation level:

| Tier | Meaning | Example |
|------|---------|---------|
| `auto` | Can be executed automatically | Create IcM ticket, send email notification |
| `gated` | Requires human approval | Create ticket for external dependency team |
| `monitor` | Schedule follow-up check | Re-run SLI check in 30 minutes |
| `recommendation` | Suggest to human operator | Scale up resources, review configuration |

### Action Selection Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   Action Selection Logic                      │
│                                                              │
│  For confirmed/contributing hypothesis:                       │
│    1. Filter action_catalog by applicable_hypotheses          │
│    2. Filter by applicable_categories                         │
│    3. Check min_confidence threshold against hypothesis       │
│       confidence                                             │
│    4. Prioritize by tier: auto > gated > monitor >           │
│       recommendation                                         │
│    5. Output structured action plan with justifications       │
│                                                              │
│  Example output:                                             │
│    Action 1: ACT-ICM-001 (auto) — Create IcM ticket         │
│      Priority: HIGH, Confidence: 0.65                        │
│      Justification: "SLI breach confirmed with outage        │
│      correlation..."                                         │
│    Action 2: ACT-EMAIL-001 (auto) — Notify AED team         │
│    Action 3: ACT-MONITOR-001 (auto) — 30-min follow-up      │
└──────────────────────────────────────────────────────────────┘
```

---

## Configuration-Driven Design

The system is designed so that **domain experts can extend detection
capabilities without changing code**. New signal types, symptoms,
hypotheses, and actions are added by editing JSON configuration files.

### Extension Points

| To Add | Edit This File | No Code Change Needed |
|--------|---------------|----------------------|
| New signal type | `config/signals/signal_template.json` | ✓ (if MCP tool exists) |
| New symptom template | `config/symptoms/<category>.json` | ✓ |
| New hypothesis | `config/hypotheses/<category>.json` | ✓ |
| New evidence requirement | `config/evidence/evidence_requirements.json` | ✓ |
| New remediation action | `config/actions/action_catalog.json` | ✓ |
| New dependency service | `config/dependency_services/<service>.json` | ✓ |
| New monitoring target | `config/monitoring_context.json` | ✓ |

### Adding a New Hypothesis (Example)

To add a hypothesis for detecting a new root cause pattern:

```json
{
  "id": "HYP-SLI-006",
  "name": "DNS Resolution Failure Caused SLI Breach",
  "statement": "The SLI breach was caused by DNS resolution failures...",
  "category": "sli",
  "expected_symptoms": ["SYM-SLI-001", "SYM-SLI-005", "SYM-DEP-001"],
  "min_symptoms_for_match": 2,
  "evidence_needed": ["ER-DEP-002", "ER-SLI-001"],
  "supporting_signals": "Strongest when cross-region pattern appears..."
}
```

No code changes required. The hypothesis scorer will automatically include
it in the next evaluation cycle, and the `prompt_loader` will inject the
updated hypothesis ID list into agent prompts via the
`{{VALID_HYPOTHESIS_IDS}}` template variable (see below).

### Prompt Template Variables

`prompt_loader.py` resolves template placeholders at startup so that
prompts stay in sync with configuration files:

| Variable | Source | Purpose |
|----------|--------|---------|
| `{{ACTION_CATALOG}}` | `config/actions/action_catalog.json` | Full action catalog JSON injected into the action-planner prompt |
| `{{VALID_HYPOTHESIS_IDS}}` | `config/hypotheses/*.json` | Auto-generated list of all valid hypothesis IDs, grouped by category, injected into reasoner & action-planner prompts |

This means adding or removing a hypothesis JSON entry is the **only** step
needed — no prompt files or code need to be edited.

---

## Agent Roster

### Analysis Agents (User-Interactive GroupChat)

| Agent | Role | Tools | Model |
|-------|------|-------|-------|
| `orchestrator` | Routes queries to specialist agents | None | gpt-4o |
| `entity_extractor` | Extracts and normalizes entities | `normalize_entity_mapping_tool` | gpt-4o |
| `outage_analyst` | Outage/incident T-SQL analysis | `run_tsql_query_tool`, `collect_root_cause_tool` | gpt-4o |
| `airo_analyst` | AIRO impact metrics analysis | `run_tsql_query_tool` | gpt-4o |
| `customer_insights` | Customer impact analysis | `run_tsql_query_tool` | gpt-4o |
| `analyst_coordinator` | Parallel analyst dispatch | Sub-agents (outage, airo, customer) | gpt-4o |
| `visualizer` | Generates Streamlit visualization code | None | gpt-4o |
| `summarizer` | Consolidates analysis into structured response | None | gpt-4o |

### Investigation Agents (Automated Pipeline)

| Agent | Role | Tools | Model |
|-------|------|-------|-------|
| `investigation_orchestrator` | Phase routing and turn management | None | gpt-4o |
| `triage_agent` | Signal → symptom matching | `collect_impacted_resource_customer_tool` | gpt-4o |
| `evidence_planner` | Evidence collection coordination | Sub-agents (collectors) | gpt-4o |
| `sli_collector` | SLI breach data collection | `collect_impacted_resource_*_tool` | gpt-4o |
| `incident_collector` | IcM incident data collection | `collect_incident_details_tool` | gpt-4o |
| `support_collector` | Support case data collection | `collect_support_request_tool` | gpt-4o |
| `reasoner` | Evidence evaluation and verdict | None (pure reasoning) | gpt-4o |
| `action_planner` | Remediation action selection | None (pure reasoning) | gpt-4o |

---

## Middleware Stack

Every agent in the pipeline is wrapped with a configurable middleware stack
that provides cross-cutting concerns:

```
┌──────────────────────────────────────────────────────────────┐
│                    Middleware Stack                            │
│                                                              │
│  ┌────────────────────────────────┐                          │
│  │ Prompt Injection Detection     │ ← Pre-execution guard    │
│  │ (Azure AI Content Safety)      │    Short-circuits on     │
│  │                                │    detected injection    │
│  └──────────────┬─────────────────┘                          │
│                 │                                             │
│  ┌──────────────▼─────────────────┐                          │
│  │ LLM Call Logging               │ ← Captures model,       │
│  │                                │    duration, errors      │
│  └──────────────┬─────────────────┘                          │
│                 │                                             │
│  ┌──────────────▼─────────────────┐                          │
│  │ Tool Call Capture              │ ← Records tool name,     │
│  │                                │    arguments, result,    │
│  │                                │    timing, agent         │
│  └──────────────┬─────────────────┘                          │
│                 │                                             │
│  ┌──────────────▼─────────────────┐                          │
│  │ Output Evaluation              │ ← Sends agent output to  │
│  │ (External eval API)            │    evaluation endpoint   │
│  └────────────────────────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

| Middleware | Type | Feature Flag | Per-Agent Toggle |
|-----------|------|-------------|-----------------|
| `PromptInjectionMiddleware` | `AgentMiddleware` | `ENABLE_PROMPT_INJECTION` | `"prompt_injection": true` |
| `LLMLoggingMiddleware` | `AgentMiddleware` | `ENABLE_LLM_LOGGING` | Always on when enabled |
| `ToolCallCaptureMiddleware` | `FunctionMiddleware` | Always on | Always on |
| `OutputEvaluationMiddleware` | `AgentMiddleware` | `ENABLE_AGENT_EVALUATION` | `"evaluate": true` |

---

## MCP Integration

The system uses the **Model Context Protocol (MCP)** to access external data
sources. All data collection happens through MCP tools served by the RATIO
MCP Server.

**File:** `src/core/mcp_integration.py`

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Architecture                               │
│                                                                  │
│  Customer Agent                          RATIO MCP Server        │
│  ┌───────────────┐                      ┌───────────────────┐   │
│  │ Agent / Signal │──── HTTP/SSE ───────▶│  MCP Endpoint     │   │
│  │ Builder        │     + Auth headers   │  /mcp             │   │
│  │                │     + X-User-Token   │                   │   │
│  │ MCPStreamable- │     + X-XCV          │  ┌─────────────┐ │   │
│  │ HTTPTool       │                      │  │ Kusto Query │ │   │
│  └───────────────┘                      │  │ Engine      │ │   │
│                                          │  └─────────────┘ │   │
│  Auth: DefaultAzureCredential            │  ┌─────────────┐ │   │
│        + CertificateCredential (KV)      │  │ IcM API     │ │   │
│        + User token pass-through         │  └─────────────┘ │   │
│                                          └───────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Tool Modes

Agents are configured with different tool access levels:

| Mode | Behavior | Example Agents |
|------|----------|---------------|
| `none` | No MCP tools | orchestrator, reasoner, action_planner |
| `filtered` | Only specified MCP tools | sli_collector, incident_collector |
| `all` | All available MCP tools | (not currently used) |
| `agent_tools` | Sub-agent invocation (no MCP) | evidence_planner, analyst_coordinator |

---

## Observability & Telemetry

**File:** `src/helper/agent_logger.py`

The `AgentLogger` singleton provides comprehensive telemetry across the
entire pipeline, publishing events to **Azure Application Insights** and
optionally to a **UI event queue** for real-time streaming.

### Event Categories

| Category | Events | Purpose |
|----------|--------|---------|
| **Signal Building** | `SignalEvaluationStart`, `MCPCollectionCall`, `SignalTypeEvaluated`, `CompoundEvaluated`, `SignalDecision` | Track data collection and activation decisions |
| **Investigation Lifecycle** | `InvestigationCreated`, `PhaseTransition`, `WorkflowStarted` | Track investigation state machine |
| **Hypothesis Tracking** | `HypothesisScoring`, `HypothesisSelected`, `HypothesisTransition` | Track hypothesis evaluation progress |
| **Agent Activity** | `AgentInvoked`, `AgentResponse`, `OutputParsed`, `SpeakerSelected` | Track individual agent turns |
| **Evidence** | `EvidenceCycle`, `ToolCall` | Track data collection during investigation |
| **Security** | `PromptInjectionDetection` | Track prompt injection attempts |

### Correlation (XCV)

All events within a single pipeline run share a **correlation vector (XCV)**
for end-to-end tracing:

```
XCV: CA-20260420-143022-a1b2c3d4

  SignalEvaluationStart    ──┐
  MCPCollectionCall (×4)   ──┤
  SignalTypeEvaluated (×4) ──┤  All share same XCV
  CompoundEvaluated (×2)   ──┤
  SignalDecision           ──┤
  InvestigationCreated     ──┤
  PhaseTransition (×7)     ──┤
  AgentInvoked (×6)        ──┤
  ToolCall (×8)            ──┤
  HypothesisScoring        ──┤
  HypothesisSelected (×2)  ──┤
  HypothesisTransition     ──┘
```

---

## Entry Points

### One-Shot Run

```bash
python run_signal_builder.py [--customer "BlackRock, Inc"] [--service-tree-id "49c39e84-..."]
```

Evaluates signals once and runs investigations for any actionable results.
Uses CLI arguments or falls back to `config/monitoring_context.json`.

### Continuous Loop

```bash
python run_signal_builder_loop.py [--interval 60]
```

Polls on a timer (default: `poll_interval_minutes` from monitoring context).
Automatically triggers investigations when signals activate. Press Ctrl+C to stop.

### API Server

```bash
python src/server/app.py
```

FastAPI server on port 8503 with SSE streaming for real-time investigation
event delivery. Exposes `/api/run` and `/api/stream` endpoints.

---

## Project Structure

```
Code/CustomerAgent/
├── run_signal_builder.py           ← One-shot entry point
├── run_signal_builder_loop.py      ← Continuous polling entry point
├── requirements.txt                ← Python dependencies
├── .env                            ← Environment variables (not committed)
│
├── src/
│   ├── server/
│   │   └── app.py                  ← FastAPI server (SSE streaming)
│   │
│   ├── core/
│   │   ├── signals/
│   │   │   ├── signal_builder.py   ← Deterministic signal evaluation engine
│   │   │   ├── signal_models.py    ← Data models (ActivatedSignal, CompoundSignal, etc.)
│   │   │   └── symptom_matcher.py  ← Symptom template loader and formatter
│   │   │
│   │   ├── investigation/
│   │   │   ├── investigation_runner.py       ← GroupChat orchestration + event streaming
│   │   │   ├── investigation_state.py        ← Data models (Investigation, Hypothesis, etc.)
│   │   │   ├── investigation_output_parser.py← Agent output → investigation state mutations
│   │   │   ├── hypothesis_scorer.py          ← Programmatic hypothesis scoring (Stage 2)
│   │   │   └── investigation_speaker_selector.py ← Custom speaker selection (reserved)
│   │   │
│   │   ├── agent_factory.py        ← Config-driven agent creation
│   │   ├── mcp_integration.py      ← MCP tool creation with auth
│   │   ├── prompt_loader.py        ← Prompt file loading + template variable injection ({{ACTION_CATALOG}}, {{VALID_HYPOTHESIS_IDS}})
│   │   └── orchestrator.py         ← User-interactive GroupChat orchestrator
│   │   │
│   │   └── middleware/
│   │       ├── tool_capture_middleware.py      ← MCP tool call recording
│   │       ├── eval_middleware.py              ← Output evaluation API integration
│   │       ├── prompt_injection_middleware.py  ← Prompt injection detection
│   │       └── llm_logging_middleware.py       ← LLM call diagnostics
│   │
│   ├── helper/
│   │   ├── agent_logger.py         ← Telemetry (App Insights + UI event queue)
│   │   ├── auth.py                 ← Azure auth (DefaultAzureCredential, MCP bearer)
│   │   └── llm.py                  ← LLM client factory (Azure OpenAI)
│   │
│   ├── config/                     ← All configuration (see Configuration Hierarchy)
│   ├── prompts/                    ← Agent instruction prompts (.txt files)
│   ├── knowledge/                  ← Shared knowledge docs appended to prompts
│   ├── a2a/                        ← Google A2A protocol support (discovery)
│   └── UI/                         ← Web UI components (cards, etc.)
```

---

## Appendix: Investigation State Machine

The `Investigation` dataclass (`investigation_state.py`) is the central
mutable state object that flows through the entire pipeline:

```
Investigation
├── id: str                        ← Unique investigation ID
├── phase: InvestigationPhase      ← Current lifecycle phase
├── context: InvestigationContext   ← Customer, service, region, severity
├── symptoms: List[Symptom]        ← Confirmed symptoms (from triage)
├── hypotheses: List[Hypothesis]   ← Ranked hypotheses (from scorer)
│   └── Hypothesis
│       ├── status: HypothesisStatus  ← ACTIVE / CONFIRMED / REFUTED / CONTRIBUTING
│       ├── match_score: float        ← 0–5 normalized score from hypothesis scorer
│       ├── confidence: float         ← Updated by reasoner
│       ├── matched_symptoms: List    ← Symptoms supporting this hypothesis
│       ├── evidence_needed: List     ← ER-IDs required for verification
│       ├── evidence_collected: List  ← ER-IDs already collected
│       ├── evidence_delta: List      ← ER-IDs still needed
│       ├── verdicts: Dict            ← Evidence verdicts per ER-ID
│       └── symptom_verdicts: Dict    ← Per-symptom verdict from reasoner
├── evidence_plan: List[ER]        ← Evidence requirements
├── evidence: List[EvidenceItem]   ← Collected evidence items
├── actions: List[Dict]            ← Selected remediation actions
├── evidence_cycles: int           ← How many collect→reason cycles
└── signal_builder_result          ← Link to triggering signals
```

### Status Transitions

```
                    ┌──────────┐
                    │  ACTIVE  │ ← Initial state after scoring
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
     ┌────────▼───┐ ┌───▼──────┐ ┌▼───────────┐
     │ CONFIRMED  │ │ REFUTED  │ │CONTRIBUTING│
     │            │ │          │ │            │
     │ Evidence   │ │ Evidence │ │ Partial    │
     │ strongly   │ │ refutes  │ │ evidence   │
     │ supports   │ │ this     │ │ supports   │
     └────────────┘ └──────────┘ └────────────┘
```

---

*This document describes the design as implemented. For contribution guidelines,
see `docs/contributing-to-customer-agent.md`.*
