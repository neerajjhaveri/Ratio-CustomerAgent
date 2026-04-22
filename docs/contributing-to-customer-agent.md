# Contributing to the Customer Agent

## Overview

The **Customer Agent** is a multi-agent investigation system built on the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python). It uses abductive reasoning to investigate customer incidents end-to-end: from signal ingestion through hypothesis generation, evidence collection, reasoning, and recommended actions.

The system consists of two main surfaces:

- **Backend** — A Python FastAPI service (port 8000) that hosts Agent Framework agents, tools, and workflows. A separate Customer Agent service runs on port 8020.
- **Frontend** — A React 18 + TypeScript SPA with a dedicated dark-themed layout at `/customer-agent`.

This guide covers how to contribute to both sides.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Backend services |
| Node.js | 18+ | Frontend dev server |
| Azure CLI | Latest | `az login` for `DefaultAzureCredential` |
| VS Code | Latest | Recommended editor |
| Git | Latest | Source control |

You also need:

- An Azure subscription with access to Azure OpenAI and Kusto (ADX)
- A `.env` file configured from `.env.example` (see [Environment Setup](#environment-setup))

---

## Project Architecture

### High-Level Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11+ · FastAPI · Uvicorn · Pydantic v2 |
| AI | Microsoft Agent Framework v1.0.1 (`Agent` + `@tool` + `AgentSession`) · `FoundryChatClient` · Azure OpenAI |
| Frontend | React 18 · Vite · TypeScript |
| Data | Azure Kusto (ADX) |

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| `agents` | 8000 | Agent orchestration API |
| `customer-agent` | 8020 | Customer Agent investigation service |
| `eval` | 8011 | Evaluation sidecar |
| `frontend` (docker) | 3000 | Production (nginx) |
| `frontend` (dev) | 3010 | Vite dev server |
| `agents-devui` | 8090 | Agent Framework DevUI |

### Project Layout

```
RATIO-AI/
├── Code/
│   ├── Frontend/                 # React 18 + Vite + TypeScript
│   │   └── src/
│   │       ├── api/              # API client modules
│   │       │   ├── agentFrameworkClient.ts   # Agent Framework (port 8000)
│   │       │   └── customerAgentClient.ts    # Customer Agent (port 8020)
│   │       ├── components/       # Reusable UI components
│   │       ├── hooks/            # Custom React hooks
│   │       ├── pages/
│   │       │   ├── customer-agent/   # Customer Agent pages
│   │       │   │   ├── ChaLayout.tsx
│   │       │   │   ├── ChaHomePage.tsx
│   │       │   │   ├── ChaScenariosPage.tsx
│   │       │   │   ├── ChaActivePage.tsx
│   │       │   │   └── ...
│   │       │   └── HomePage.tsx
│   │       ├── types/
│   │       └── App.tsx           # Root component with routing
│   ├── Servers/
│   │   ├── agents/               # Agent orchestration (port 8000)
│   │   │   ├── agents/           # Agent class definitions
│   │   │   ├── tools/            # @tool functions
│   │   │   ├── workflows/        # Multi-agent orchestration
│   │   │   ├── providers/        # Agent Framework provider
│   │   │   └── app_kernel.py     # FastAPI entry point
│   │   └── eval/                 # Evaluation sidecar (port 8011)
│   └── Shared/                   # Cross-cutting libraries
│       ├── api/                  # Response utilities
│       ├── clients/              # Azure clients (chat, kusto)
│       ├── config/               # Settings management
│       └── middleware/           # Security, logging, eval, error
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

### How Frontend and Backend Connect

In development, Vite proxies API requests to the backend services:

- `/api/af/*` → `http://127.0.0.1:8000` (Agent Framework)
- `/customer-agent-api/*` → `http://127.0.0.1:8020` (Customer Agent)

The frontend never calls `fetch()` directly in components — all HTTP calls go through typed API client modules in `src/api/`.

---

## Getting Started

### 1. Clone the repo

```bash
git clone <repo-url> RATIO-AI
cd RATIO-AI
```

### 2. Environment Setup

Copy the example env file and fill in your Azure credentials:

```bash
cp .env.example .env
```

Key variables to configure:

```env
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1-mini
AZURE_AI_PROJECT_ENDPOINT=https://your-endpoint.services.ai.azure.com/api/projects/your-project
AZURE_TENANT_ID=your-tenant-id
KUSTO_ICM_CLUSTER_URI=https://your-cluster.kusto.windows.net
KUSTO_ICM_DATABASE=Common
APP_ENV=development
```

### 3. Install Backend Dependencies

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd Code/Frontend
npm install
cd ../..
```

### 5. Run Locally

The easiest way to start everything:

```powershell
.\Code\scripts\start_all.ps1
```

This starts all four services (agents, eval, devui, frontend) in parallel. Press `Ctrl+C` to stop all.

Alternatively, start services individually:

```bash
# Backend (agents)
cd Code/Servers/agents
uvicorn app_kernel:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd Code/Frontend
npm run dev
```

### 6. Verify

- Agent API health: `http://localhost:8000/health`
- Customer Agent health: `http://localhost:8020/health`
- Frontend: `http://localhost:3010`
- Customer Agent UI: `http://localhost:3010/customer-agent`
- DevUI: `http://localhost:8090`

---

## Contributing to the Backend (Servers)

The backend uses the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python) for agent orchestration. Key concepts:

- **`Agent`** — an LLM-powered agent with instructions, tools, and context providers
- **`@tool`** — decorator that exposes a Python function to agents as a callable tool
- **`AgentSession`** — manages multi-turn conversation state
- **`FoundryChatClient`** — connects to Azure Foundry/OpenAI

### How to Add a New Agent Tool

Tools are Python functions decorated with `@tool` that agents can invoke during conversations. See the [Agent Framework tools documentation](https://learn.microsoft.com/en-us/agent-framework/agents/tools/) for full details.

**Step 1.** Create or open a tool file in `Code/Servers/agents/tools/`. Tool files follow the `*_tools.py` naming convention.

```python
# Code/Servers/agents/tools/incident_tools.py

from __future__ import annotations

import logging
from typing import Annotated

from agent_framework import tool
from pydantic import Field

logger = logging.getLogger(__name__)


@tool(approval_mode="never_require")
def get_incident_timeline(
    incident_id: Annotated[str, Field(description="The IcM incident ID")],
) -> str:
    """Retrieve the timeline of events for a specific incident.

    Use this tool when you need to understand the chronological sequence
    of actions taken during an incident investigation.
    """
    # Implementation here
    try:
        from Code.Shared.clients.kusto_client import query_kql
        results = query_kql(
            cluster="https://icmdataro.centralus.kusto.windows.net",
            database="IcMDataWarehouse",
            query=f"IncidentHistory | where IncidentId == '{incident_id}' | order by Timestamp asc",
        )
        return json.dumps(results, default=str)
    except Exception as exc:
        logger.error("Failed to get incident timeline: %s", exc)
        return json.dumps({"error": str(exc)})


# Export all tools as a list (convention)
ALL_INCIDENT_TOOLS = [get_incident_timeline]
```

Key rules for tools:

- The **docstring** is critical — it tells the LLM when and how to use the tool
- Use `Annotated[type, Field(description="...")]` for all parameters
- Set `approval_mode="never_require"` for tools that don't need user confirmation
- Return `str` (typically JSON) — agents parse the string response
- Use `logging.getLogger(__name__)` — never `print()`

**Step 2.** Register tools with the agent in `providers/af_provider.py`:

```python
# Import the new tools
try:
    from tools.incident_tools import ALL_INCIDENT_TOOLS
except ImportError:
    ALL_INCIDENT_TOOLS = []

# Add to agent configs
AGENT_CONFIGS = {
    "Data_Analyst_Agent": {
        "instructions": "You analyze incident data...",
        "tools": ALL_KUSTO_TOOLS + ALL_INCIDENT_TOOLS,  # Add here
    },
}
```

**Step 3.** Test the tool:

```python
# Code/Servers/agents/tests/test_incident_tools.py

import pytest
from unittest.mock import patch


def test_get_incident_timeline_returns_json():
    from tools.incident_tools import get_incident_timeline

    with patch("tools.incident_tools.query_kql") as mock_kql:
        mock_kql.return_value = [{"IncidentId": "123", "Action": "Created"}]
        result = get_incident_timeline("123")
        assert '"IncidentId"' in result
        mock_kql.assert_called_once()
```

### How to Add a New API Endpoint

API endpoints live in `Code/Servers/agents/app_kernel.py`. Follow these patterns:

```python
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field


# Define request/response schemas with Pydantic v2
class AnalysisRequest(BaseModel):
    incident_id: str = Field(..., min_length=1, max_length=100)
    depth: int = Field(default=3, ge=1, le=10)


class AnalysisResponse(BaseModel):
    incident_id: str
    summary: str
    findings: list[str]


@app.post("/api/af/analyze", response_model=AnalysisResponse, status_code=200)
async def analyze_incident(request: AnalysisRequest):
    """Run an agent-powered analysis of an incident."""
    try:
        from providers.af_provider import create_agent, run_agent, AGENT_CONFIGS

        agent = create_agent(
            name="Data_Analyst_Agent",
            instructions=AGENT_CONFIGS["Data_Analyst_Agent"]["instructions"],
            tools=AGENT_CONFIGS["Data_Analyst_Agent"].get("tools"),
        )
        result = await run_agent(agent, f"Analyze incident {request.incident_id}")
        return AnalysisResponse(
            incident_id=request.incident_id,
            summary=result,
            findings=[],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

Rules:

- **Always** use `async def` for route handlers
- **Always** set `response_model=` on routes
- Use `Pydantic v2` for request/response schemas
- Raise `HTTPException` with specific status codes — never return error bodies with 200
- Every service must have a `GET /health` endpoint

### How to Add a Workflow Orchestration

Workflows compose multiple agents into collaborative patterns. See the [Agent Framework workflows documentation](https://learn.microsoft.com/en-us/agent-framework/workflows/) for full details.

Workflows live in `Code/Servers/agents/workflows/workflows.py`:

```python
from agent_framework import Agent
from agent_framework_orchestrations import (
    SequentialBuilder,
    ConcurrentBuilder,
    HandoffBuilder,
    GroupChatBuilder,
)
from providers.af_provider import create_agent, get_chat_client


def build_investigation_workflow(session_id: str | None = None):
    """Build a sequential investigation workflow.

    Agents process in order: Triage → Evidence → Reasoning → Action.
    """
    triage = create_agent(
        name="Triage_Agent",
        instructions="You triage incoming signals and classify severity...",
        tools=[],
        session_id=session_id,
    )
    evidence = create_agent(
        name="Evidence_Agent",
        instructions="You collect supporting evidence from telemetry...",
        tools=ALL_KUSTO_TOOLS,
        session_id=session_id,
    )

    workflow = SequentialBuilder(participants=[triage, evidence]).build()
    return workflow
```

Available orchestration builders:

| Builder | Pattern | Use When |
|---------|---------|----------|
| `SequentialBuilder` | Agents process in order | Pipeline stages (triage → evidence → action) |
| `ConcurrentBuilder` | Agents work in parallel | Independent data collection tasks |
| `HandoffBuilder` | Agents delegate to each other | Specialist routing |
| `GroupChatBuilder` | Multi-agent discussion | Complex reasoning requiring debate |

### Testing Backend Changes

```bash
# Run all tests
pytest -v

# Run a specific test file
pytest Code/Servers/agents/tests/test_health.py -v

# Run with async support
pytest -v --asyncio-mode=auto
```

Test pattern for async endpoints:

```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_endpoint():
    from app_kernel import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "ok")
```

---

## Contributing to the Frontend

The frontend is a React 18 + TypeScript app using Vite. The Customer Agent has its own full-screen layout separate from the main app.

### Routing Architecture

In `App.tsx`, routes under `/customer-agent` use `ChaLayout` (a dark-themed sidebar with its own navigation), while all other routes use the main `Sidebar` layout:

```tsx
// App.tsx — simplified routing logic
function AppLayout() {
  const location = useLocation();
  const isCustomerAgent = location.pathname.startsWith('/customer-agent');

  if (isCustomerAgent) {
    return (
      <Routes>
        <Route path="/customer-agent" element={<ChaLayout />}>
          <Route index element={<ChaHomePage />} />
          <Route path="scenarios" element={<ChaScenariosPage />} />
          <Route path="active" element={<ChaActivePage />} />
          <Route path="history" element={<ChaHistoryPage />} />
          <Route path="agents" element={<ChaAgentsPage />} />
          <Route path="config" element={<ChaConfigPage />} />
          <Route path="data" element={<ChaDataPage />} />
          <Route path="knowledge" element={<ChaKnowledgePage />} />
        </Route>
      </Routes>
    );
  }
  // ... main app routes
}
```

### How to Add a New Customer Agent Page

**Step 1.** Create the page component in `src/pages/customer-agent/`:

```tsx
// src/pages/customer-agent/ChaMetricsPage.tsx

import { useEffect, useState } from 'react';

interface MetricsSummary {
  total_investigations: number;
  avg_duration_min: number;
  success_rate: number;
}

export default function ChaMetricsPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/customer-agent-api/api/metrics')
      .then(r => r.json())
      .then(setMetrics)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading metrics...</div>;

  return (
    <>
      <h2>Investigation Metrics</h2>
      {metrics && (
        <div className="cha-card-grid">
          <div className="cha-card">
            <div className="cha-card-header">
              <div className="cha-card-title">Total Investigations</div>
            </div>
            <div className="cha-card-body">
              <span className="cha-metric">{metrics.total_investigations}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

**Step 2.** Add the route in `App.tsx`:

```tsx
import ChaMetricsPage from './pages/customer-agent/ChaMetricsPage';

// Inside the ChaLayout routes:
<Route path="metrics" element={<ChaMetricsPage />} />
```

**Step 3.** Add navigation in `ChaLayout.tsx`. Add an entry to the `NAV` array:

```tsx
const NAV = [
  // ... existing entries
  { section: 'ANALYTICS' },
  { to: 'metrics', icon: 'fa-chart-bar', label: 'Metrics' },
] as const;
```

And add the page title:

```tsx
const PAGE_TITLES: Record<string, string> = {
  // ... existing entries
  'metrics': 'Investigation Metrics',
};
```

### How to Add an API Client Function

All API calls live in `src/api/`. The Customer Agent client is `customerAgentClient.ts`.

**Pattern:** The client uses a typed `oaFetch` wrapper that handles errors and JSON parsing:

```typescript
// src/api/customerAgentClient.ts

// 1. Define the response type
export interface MetricsSummary {
  total_investigations: number;
  avg_duration_min: number;
  success_rate: number;
}

// 2. Add the API function
export async function getMetrics(): Promise<MetricsSummary> {
  return oaFetch('/api/metrics');
}
```

For SSE streaming endpoints, use the async generator pattern:

```typescript
export async function* streamInvestigation(
  scenarioId: string,
  signal?: AbortSignal,
): AsyncGenerator<InvestigationEvent> {
  const res = await fetch(`${PREFIX}/api/investigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Failed to start investigation: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      while (buffer.includes('\n\n')) {
        const idx = buffer.indexOf('\n\n');
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              yield JSON.parse(line.slice(6)) as InvestigationEvent;
            } catch { /* skip malformed JSON */ }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

### How to Add a New Component

Reusable components live in `src/components/`. Use the following conventions:

```tsx
// src/components/common/StatusBadge.tsx

interface StatusBadgeProps {
  status: 'connected' | 'disconnected' | 'pending';
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const classMap = {
    connected: 'cha-badge-handled',
    disconnected: 'cha-badge-error',
    pending: 'cha-badge-watching',
  };

  return (
    <span className={`cha-badge ${classMap[status]}`}>
      {label ?? status}
    </span>
  );
}
```

Rules:

- Functional components only — no class components
- Define a `Props` interface above every component
- Export from the barrel file (`components/index.ts`) for shared components
- Use CSS classes from `cha-theme.css` — no inline styles
- Components never call `fetch()` directly — use API client modules

### Testing Frontend Changes

```bash
cd Code/Frontend
npm run build    # Type-check + build (catches TypeScript errors)
npm run dev      # Start dev server and test manually
```

---

## Shared Code (`Code/Shared/`)

The `Shared/` directory contains cross-cutting libraries used by all backend services. Never duplicate this logic in individual services.

### Middleware (`Code/Shared/middleware/`)

All agent middleware is defined here. Import the default stack:

```python
from Code.Shared.middleware import build_default_middleware

middleware = build_default_middleware(
    enable_eval=True,
    enable_prompt_injection=True,
)
```

The default stack includes:

| Middleware | Purpose |
|-----------|---------|
| `LoggingAgentMiddleware` | Structured logging with timing |
| `ToolTimingMiddleware` | Function call logging |
| `SecurityMiddleware` | Blocks sensitive content |
| `ErrorHandlingMiddleware` | Graceful tool failures |
| `PromptInjectionMiddleware` | Screens prompts for injection |
| `EvalMiddleware` | Post-execution quality scoring |
| `ContentFilterMiddleware` | Azure Content Safety |

See the [Agent Framework middleware documentation](https://learn.microsoft.com/en-us/agent-framework/agents/middleware/) for details on the middleware pipeline.

### Clients (`Code/Shared/clients/`)

- `chat_client.py` — Cached `FoundryChatClient` singleton for Azure OpenAI
- `kusto_client.py` — Kusto query helper (`query_kql()`)

### Config (`Code/Shared/config/`)

- `settings.py` — Pydantic `BaseSettings` for environment variable management

### Import Conventions

**Service-local imports** (within `Code/Servers/agents/`):

```python
from tools.kusto_tools import ALL_KUSTO_TOOLS         # ✅
from providers.af_provider import create_agent          # ✅
```

**Shared imports** (always with fallback):

```python
try:
    from Code.Shared.middleware import build_default_middleware
except ImportError:
    build_default_middleware = None                      # ✅
```

**Never do:**

```python
from Code.Servers.agents.tools.kusto_tools import ...   # ❌ use service-local
from .tools import ...                                   # ❌ no relative imports
from Shared.config import ...                            # ❌ always prefix Code.
```

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Unawaited coroutines | Every `async` call must be `await`ed |
| Blocking in async context | Use `httpx`/`aiohttp`, never `requests` or `time.sleep()` in async functions |
| Circular imports | Dependency direction: Agents → Tools → Models |
| Wrong import style | Service-local absolute imports inside services, `Code.Shared.*` for shared |
| Missing `try/except ImportError` | Always guard shared imports with fallback |
| Using `print()` | Use `logging.getLogger(__name__)` everywhere |
| `allow_origins=["*"]` in CORS | Use explicit origin list |
| Reading `os.environ` directly for config | Use `pydantic-settings` `BaseSettings` class |
| Unpinned dependencies | Always pin in `requirements.txt` |
| Components calling `fetch()` directly | All HTTP calls go through `src/api/` client modules |
| Using `any` in TypeScript | Avoid — use proper types. Comment why if truly unavoidable |
| Inline styles in React | Use CSS classes from theme files |
| Returning error bodies with HTTP 200 | Raise `HTTPException` with correct status code |

---

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case` | `kusto_tools.py` |
| Classes | `PascalCase` | `ManagerAgent` |
| Functions & variables | `snake_case` | `create_agent` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Agent files | `*_agent.py` | `planner_agent.py` |
| Tool files | `*_tools.py` | `kusto_tools.py` |
| Test files | `test_*.py` | `test_health.py` |
| React pages | `PascalCase.tsx` | `ChaHomePage.tsx` |
| API clients | `camelCase.ts` | `customerAgentClient.ts` |
| React hooks | `use*.ts` | `useInvestigation.ts` |
| Env vars | `UPPER_SNAKE_CASE` | `AZURE_OPENAI_ENDPOINT` |
| Middleware | `PascalCase` + `Middleware` | `SecurityMiddleware` |

Customer Agent pages use the `Cha` prefix (short for **C**ustomer **H**ealth **A**gent):

- Pages: `ChaHomePage.tsx`, `ChaScenariosPage.tsx`, etc.
- Layout: `ChaLayout.tsx`
- Theme: `cha-theme.css`
- CSS classes: `cha-*` prefix (e.g., `cha-card`, `cha-badge`, `cha-btn-primary`)

---

## Further Reading

### Microsoft Agent Framework

- [Overview](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python)
- [Tools](https://learn.microsoft.com/en-us/agent-framework/agents/tools/) — `@tool` decorator, parameter annotations, approval modes
- [Sessions](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/session) — `AgentSession`, conversation history, state management
- [Middleware](https://learn.microsoft.com/en-us/agent-framework/agents/middleware/) — before/after hooks, middleware pipeline
- [Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/) — Sequential, Concurrent, Handoff, GroupChat orchestration

### Project Resources

- [README](../README.md) — Project overview and quickstart
- [`.env.example`](../.env.example) — Environment variable reference
- [`docker-compose.yml`](../docker-compose.yml) — Container orchestration
- [`start_all.ps1`](../Code/scripts/start_all.ps1) — Local development startup
- DevUI — `http://localhost:8090` for visual agent debugging
