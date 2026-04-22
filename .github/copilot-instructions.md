# GitHub Copilot Instructions

## Project Overview

Agentic API server built on **Microsoft Agent Framework** with a React debugging frontend.

| Layer | Stack |
|-------|-------|
| **Backend** | Python 3.11+ · FastAPI · Uvicorn · Pydantic v2 |
| **AI** | Agent Framework v1.0.1 (`Agent` + `@tool` + `AgentSession`) · `FoundryChatClient` · Azure OpenAI |
| **Eval** | azure-ai-evaluation SDK · DeepEval |
| **Frontend** | React 18 · Vite · TypeScript |
| **Data** | Azure Kusto (ADX) · Cosmos DB (planned) |
| **DevUI** | Agent Framework DevUI (agent/workflow debugging) |

---

## Project Layout

```
├── Code/
│   ├── Frontend/             # React 18 + Vite + TypeScript
│   │   ├── src/
│   │   │   ├── api/          # API client (fetch wrappers)
│   │   │   ├── components/   # Reusable UI components
│   │   │   ├── hooks/        # Custom React hooks
│   │   │   ├── pages/        # Route-level page components
│   │   │   ├── types/        # TypeScript type definitions
│   │   │   ├── constants/    # App-wide constants
│   │   │   ├── App.tsx       # Root component
│   │   │   └── main.tsx      # Vite entry point
│   │   ├── Dockerfile        # nginx production build
│   │   └── package.json
│   ├── Servers/
│   │   ├── agents/           # Agent orchestration (port 8000)
│   │   │   ├── agents/       # Agent definitions (BaseAgent subclasses, factory pattern)
│   │   │   ├── tools/        # @tool functions (Kusto, etc.)
│   │   │   ├── workflows/    # Multi-agent orchestration flows
│   │   │   ├── providers/    # Agent Framework provider + chat client
│   │   │   ├── app_kernel.py # FastAPI app entry point
│   │   │   ├── app_config.py # Service configuration
│   │   │   ├── devui_serve.py# DevUI server
│   │   │   └── Dockerfile
│   │   └── eval/             # Evaluation sidecar (port 8011)
│   │       ├── adapters/     # External service adapters
│   │       ├── api/          # FastAPI routes
│   │       ├── core/         # Business logic
│   │       ├── models/       # Pydantic schemas
│   │       ├── tests/        # Service tests
│   │       └── Dockerfile
│   ├── Shared/               # Cross-cutting libraries
│   │   ├── api/              # Response utilities
│   │   ├── clients/          # Azure clients (chat, cosmos, kusto)
│   │   ├── config/           # Settings management
│   │   ├── evaluation/       # Eval engines + interfaces
│   │   └── middleware/       # Security, logging, eval, error, PI
│   └── scripts/
│       └── start_all.ps1     # One-command local startup
├── deploy/                   # Bicep IaC
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

---

## Python Coding Standards

### Import Conventions (Critical)

**Service-local imports** — absolute relative to the service root (enabled by `pythonpath` in `pytest.ini`):

```python
# Inside Code/Servers/agents/providers/af_provider.py
from tools.kusto_tools import ALL_KUSTO_TOOLS           # ✅ service-local
from workflows.workflows import ORCHESTRATION_BUILDERS   # ✅ service-local
```

**Shared imports** — full path from project root with graceful fallback:

```python
try:
    from Code.Shared.api.response_utils import create_success_response
except ImportError:
    create_success_response = None
```

**Never use**:
- `from Code.Servers.agents.tools.kusto_tools import ...` — use service-local
- Relative imports (`from .tools import ...`)
- Bare `from Shared.xxx import ...` — always prefix with `Code.`

### Async / Await Rules

| Rule | Do | Don't |
|------|----|-------|
| Async routes | `async def endpoint():` with `await` on all I/O | `time.sleep()`, `requests.get()` in async context |
| Sync SDK in async | `await run_in_threadpool(sync_call)` | Call sync SDK directly in async function |
| CPU-heavy work | `run_in_threadpool()` or process pool | Blocking the event loop |
| Sleep | `await asyncio.sleep(n)` | `time.sleep(n)` |
| HTTP calls | `httpx.AsyncClient` or `aiohttp` | `requests` library |

### FastAPI Best Practices

1. **Pydantic v2 for everything** — request/response schemas, config, validation
2. **Dependency injection** — use `Depends()` for auth, validation, shared resources
3. **Response models** — always set `response_model=` on routes
4. **Status codes** — explicit `status_code=` on create/update routes
5. **Health endpoints** — every service must have `GET /health` returning `{"status": "ok"}`
6. **Error handling** — raise `HTTPException` with specific status codes, never return error bodies with 200
7. **CORS** — explicit origin list, never `allow_origins=["*"]` in production
8. **Logging** — `logging.getLogger(__name__)` everywhere, never `print()`
9. **Config** — `pydantic-settings` `BaseSettings` class, never read `os.environ` directly

### Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case` | `agent_factory.py` |
| Classes | `PascalCase` | `ManagerAgent`, `SecurityMiddleware` |
| Functions & vars | `snake_case` | `create_agent`, `session_id` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_PORT` |
| Agent files | `*_agent.py` | `planner_agent.py` |
| Tool files | `*_tools.py` | `kusto_tools.py` |
| Test files | `test_*.py` | `test_health.py` |
| Env vars | `UPPER_SNAKE_CASE` | `AZURE_OPENAI_ENDPOINT` |
| Middleware | `PascalCase` + `Middleware` | `EvalMiddleware` |

### Pydantic Patterns

```python
# ✅ Request/Response schemas with explicit field constraints
from pydantic import BaseModel, Field

class AgentRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4096)
    session_id: str | None = None
    max_rounds: int = Field(default=4, ge=1, le=20)

# ✅ Config via BaseSettings (auto-reads env vars)
from pydantic_settings import BaseSettings

class ServiceConfig(BaseSettings):
    port: int = 8000
    debug: bool = False
    azure_openai_endpoint: str

    class Config:
        env_prefix = ""
        case_sensitive = False
```

### Testing Standards

- Framework: **pytest** + `@pytest.mark.asyncio`
- Async client: **httpx** `AsyncClient` with `ASGITransport` (not `TestClient` for async)
- Mock externals: Azure OpenAI, Kusto, Cosmos — never call live services in tests
- Test file naming: `test_<module>.py` inside service `tests/` directory
- Coverage: every new feature must include tests

```python
# ✅ Async test pattern
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_health():
    from api.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
```

---

## React / TypeScript Standards

### Component Patterns

```typescript
// ✅ Functional component with TypeScript props
interface AgentPanelProps {
  sessionId: string;
  onComplete: (result: AgentResult) => void;
}

export function AgentPanel({ sessionId, onComplete }: AgentPanelProps) {
  const [loading, setLoading] = useState(false);
  // ...
}
```

### File Organization

| Category | Location | Convention |
|----------|----------|-----------|
| Pages | `pages/` | `PascalCase.tsx` — one per route |
| Components | `components/` | `PascalCase.tsx` — reusable UI pieces |
| Hooks | `hooks/` | `use*.ts` — custom hooks |
| API calls | `api/` | `camelCase.ts` — fetch wrappers |
| Types | `types/` | `camelCase.ts` — shared interfaces |
| Constants | `constants/` | `camelCase.ts` — app-wide constants |

### Rules

1. **Functional components only** — no class components
2. **TypeScript strict mode** — no `any` unless truly unavoidable (comment why)
3. **Custom hooks** for shared logic — extract into `hooks/use*.ts`
4. **API layer separation** — all fetch calls go in `api/`, components never call `fetch()` directly
5. **No inline styles** — use CSS modules or styled-components
6. **Error boundaries** — wrap page-level components
7. **State management** — React hooks + context for local state; no Redux unless justified

---

## Agent Framework Patterns

### Creating Agents

```python
# 1. Define the agent class (agents/<name>_agent.py)
from agents.base_agent import BaseAgent
from agents.agent_factory import register_agent

@register_agent
class MyAgent(BaseAgent):
    name = "My_Agent"
    instructions = "You are a helpful assistant that..."
    tools = [my_tool]
```

```python
# 2. Register in agent_factory.py → _discover_agents()
from agents.my_agent import MyAgent  # noqa: F401
```

The `@register_agent` decorator registers the agent in the factory. The `af_provider.py` loads all configs via `get_agent_configs()` at startup.

### Key Patterns

- **`@tool` decorator** for all agent-callable functions (replaces old `@kernel_function`)
- **`AgentSession`** for multi-turn conversations with history
- **`FoundryChatClient`** as the shared LLM client singleton (via `Code.Shared.clients.chat_client`)
- **Middleware stack**: Security → Logging → ToolTiming → ErrorHandling → PromptInjection → Eval
- **DevUI** for visual debugging at `http://localhost:8090`

### Middleware

All middleware lives in `Code/Shared/middleware/`. Import the default stack:

```python
from Code.Shared.middleware import build_default_middleware

middleware = build_default_middleware(
    enable_eval=True,
    enable_prompt_injection=True,
)
```

Never create service-local middleware — extend the shared stack.

---

## Security

- **Never** commit API keys, connection strings, or tokens
- **`DefaultAzureCredential`** for Azure auth; API key fallback only when credential auth unavailable
- **CORS**: explicit origin list — never `["*"]` in production
- **Input validation**: Pydantic models on all endpoints — never trust raw input
- **Secrets**: `.env` file locally, Key Vault / App Settings in production
- **Dependencies**: pin versions in `requirements.txt`, audit regularly

---

## Service Ports (source of truth: `docker-compose.yml`)

| Service | Port | Description |
|---------|------|-------------|
| agents | 8000 | Agent orchestration API |
| eval | 8011 | Evaluation sidecar |
| frontend | 3000 | Docker (nginx); dev = 3010 |
| agents-devui | 8090 | Agent Framework DevUI |

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Unawaited coroutines | Every `async` call must be `await`ed |
| Blocking in async | Use `aiohttp`/`httpx`, never `requests`/`time.sleep()` |
| Circular imports | Direction: Agents → Tools → Models |
| Wrong import style | Service-local absolute, `Code.Shared.*` for shared |
| Missing `try/except ImportError` | Always guard shared imports |
| Using `print()` | Use `logging.getLogger(__name__)` |
| `allow_origins=["*"]` | Explicit CORS origin list |
| Raw `os.environ` | Use `pydantic-settings` BaseSettings |
| Unpinned deps | Always pin in `requirements.txt` |
| Moving Python packages deeper | Update `_CONFIG_DIR` (add `..` per level), relative imports (add `.` per level), `__init__.py` re-exports, and `@patch` target paths in tests |

---

## Skills & Agents

Reusable workflow skills are in `.github/skills/`:
- `new-agent` — Create a new Agent Framework agent (BaseAgent subclass + factory registration)
- `new-agent-tool` — Add a new `@tool` function to the agents service
- `new-api-endpoint` — Add a new FastAPI endpoint
- `new-react-page` — Add a new React page with routing

Agent definitions are in `.github/agents/`:
- `engineer` — Backend Python/FastAPI development
- `frontend` — React/TypeScript/Vite development
- `qa` — Testing, code review, linting

Targeted instructions in `.github/instructions/` load automatically by file path.
# GitHub Copilot Instructions

## Project Overview

- **Python**: 3.11+ · **Backend**: FastAPI + Uvicorn · **Frontend**: React 18 + Vite + TypeScript
- **AI Stack**: Microsoft Agent Framework (`agent-framework` v1.0.1) · `Agent` + `@tool` + `AgentSession` · `FoundryChatClient`
- **Eval**: azure-ai-evaluation SDK + DeepEval · **Data**: Azure Kusto (ADX), Cosmos DB (planned)
- **Dev UI**: Agent Framework DevUI (agent/workflow testing & debugging)

## Project Layout

| Location | What belongs |
|----------|-------------|
| `Code/Frontend/` | React 18 + Vite + TypeScript production web UI |
| `Code/Servers/agents/` | Agent orchestration service (FastAPI, port 8000) |
| `Code/Servers/eval/` | Evaluation sidecar service (FastAPI, port 8011) |
| `Code/Shared/` | Cross-cutting libraries (config, clients, eval, middleware, API utils) |
| `Code/scripts/` | Dev startup script (`start_all.ps1`) |
| `deploy/` | Infrastructure-as-code (Bicep) |

## Import Conventions (Critical)

Services use **absolute imports relative to their own root** (enabled by `pythonpath` in `pytest.ini`):

```python
# Inside Servers/agents/providers/af_provider.py
from tools.kusto_tools import ALL_KUSTO_TOOLS        # ✅ service-local
from workflows.workflows import ORCHESTRATION_BUILDERS  # ✅ service-local
```

Shared utilities use **full absolute paths from project root** with graceful fallback:

```python
try:
    from Code.Shared.api.response_utils import create_success_response
    SHARED_UTILS_AVAILABLE = True
except ImportError:
    SHARED_UTILS_AVAILABLE = False
```

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python files | `snake_case` | `agent_factory.py` |
| Classes | `PascalCase` | `ManagerAgent`, `DataAnalystTools` |
| Functions & variables | `snake_case` | `create_agent`, `session_id` |
| Agent files | `*_agent.py` | `planner_agent.py` |
| Tool files | `*_tools.py` | `kusto_tools.py` |
| Environment variables | `UPPER_SNAKE_CASE` | `AZURE_OPENAI_ENDPOINT` |
| Test files | `test_*.py` | `test_health.py` |
| TypeScript/React | `PascalCase` components, `camelCase` utils | `HomePage.tsx`, `client.ts` |
| Middleware classes | `PascalCase` + `Middleware` suffix | `SecurityMiddleware` |

## Common Pitfalls

- **Unawaited coroutines**: Every `async` call must be `await`ed
- **Blocking in async**: Never use `requests` or `time.sleep()` — use `aiohttp`, `asyncio.sleep()`
- **Circular imports**: Dependency direction is Agents → Tools → Models
- **Wrong import style**: Use service-local absolute imports, not full paths from project root
- **Shared utils guard**: Always wrap shared imports in `try/except ImportError`
- **Configuration**: Use `Code.Shared.config.settings` for all config; use `Code.Shared.clients.chat_client` for the shared `FoundryChatClient` singleton
- **Print statements**: Never use `print()` — use `logging.getLogger(__name__)`
- **Middleware location**: All agent middleware lives in `Code/Shared/middleware/`. Import via `from Code.Shared.middleware import build_default_middleware`
- **Moving Python packages deeper**: Update `_CONFIG_DIR` (add `..` per level), relative imports (add `.` per level), `__init__.py` re-exports, and `@patch` target paths in tests

## Service Ports (Source of truth: `docker-compose.yml`)

| Service | Port | Notes |
|---------|------|-------|
| `agents` | 8000 | Agent orchestration |
| `eval` | 8011 | Evaluation sidecar |
| `frontend` | 3000 | Docker (nginx); dev mode uses 3010 |
| `agents-devui` | 8090 | Agent Framework DevUI |

## Security Essentials

- **Never** commit API keys, connection strings, or tokens
- Use `DefaultAzureCredential` for Azure auth; API key fallback only when credential auth is unavailable
- CORS origins must be explicitly listed — never `allow_origins=["*"]` in production
- Validate and sanitise all user inputs in API endpoints

## Testing

- Framework: `pytest` · Run all: `pytest -v` · Single service: `pytest Code/Servers/eval/tests/ -v`
- Use `@pytest.mark.asyncio` for async tests · Mock external services (Azure AI, Kusto, OpenAI)
- New features must include tests

## Targeted Instructions

Domain-specific rules in `.github/instructions/` load automatically:
- `agents.instructions.md` → `Code/Servers/agents/**`
- `python-services.instructions.md` → `Code/Servers/**/*.py`
- `react-ui.instructions.md` → `Code/Frontend/**`
- `evaluation.instructions.md` → `Code/Servers/eval/**`
