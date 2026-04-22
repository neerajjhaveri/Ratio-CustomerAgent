# Agentic API Server

A Python-based agentic API server built on [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) and Azure AI. Ships with a React frontend for debugging via DevUI.

## Project Structure

```
├── Code/
│   ├── Frontend/          # React 18 + Vite + TypeScript (production UI)
│   ├── Servers/
│   │   ├── agents/        # Agent orchestration service (FastAPI, port 8000)
│   │   │   ├── agents/    # Agent definitions (one class per agent, factory pattern)
│   │   │   ├── tools/     # @tool functions (Kusto, etc.)
│   │   │   ├── workflows/ # Multi-agent orchestration workflows
│   │   │   ├── providers/ # Agent Framework provider
│   │   │   ├── app_kernel.py  # FastAPI app entry point
│   │   │   └── devui_serve.py # Agent Framework DevUI server
│   │   └── eval/          # Evaluation sidecar (FastAPI, port 8011)
│   ├── Shared/            # Cross-cutting libraries
│   │   ├── api/           # Response utilities
│   │   ├── clients/       # Azure clients (chat, cosmos, kusto)
│   │   ├── config/        # Settings management
│   │   ├── evaluation/    # Eval engines + interfaces
│   │   └── middleware/    # Security, logging, eval, error handling
│   └── scripts/           # Dev startup script
├── deploy/                # Bicep infrastructure-as-code
├── docker-compose.yml     # Container orchestration
├── requirements.txt       # Python dependencies
└── .env.example           # Environment variable template
```

## Prerequisites

- **Python** 3.11+
- **Node.js** 18+ (for Frontend)
- **Azure CLI** authenticated (`az login`)
- An **Azure OpenAI** deployment

## Setup

### 1. Clone and create virtual environment

```powershell
git clone <repo-url>
cd <project-name>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

```powershell
npm aud
pip install --pre agent-framework-devui
```

### 3. Install Frontend dependencies

```powershell
cd Code/Frontend
npm install
cd ..
```

### 4. Configure environment

```powershell
Copy-Item .env.example .env
# Edit .env with your Azure OpenAI endpoint, deployment name, and credentials
```

## Running Locally

### Option A: Start everything at once

```powershell
.\Code\scripts\start_all.ps1
```

This starts all services in parallel:

| Service | URL | Description |
|---------|-----|-------------|
| agents | http://127.0.0.1:8000 | Agent orchestration API |
| eval | http://127.0.0.1:8011 | Evaluation sidecar |
| agents-devui | http://127.0.0.1:8090 | Agent Framework DevUI |
| frontend | http://127.0.0.1:3010 | React dev server |

Press `Ctrl+C` to stop all services.

### Option B: Start services individually

**Backend (agents service):**

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
cd Code/Servers/agents
python -m uvicorn app_kernel:app --host 127.0.0.1 --port 8000 --reload
```

**Backend (eval sidecar):**

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
cd Code/Servers/eval
python -m uvicorn api.app:app --host 127.0.0.1 --port 8011 --reload
```

**DevUI (agent debugging):**

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
cd Code/Servers/agents
python devui_serve.py
```

**Frontend:**

```powershell
cd Code/Frontend
npm run dev
```

### Option C: Docker

```powershell
docker-compose up --build
```

| Service | Port |
|---------|------|
| agents | 8000 |
| eval | 8011 |
| frontend | 3000 (nginx) |

## Testing

```powershell
.\.venv\Scripts\Activate.ps1
pytest -v                          # Run all tests
pytest Code/Servers/eval/tests/ -v      # Single service
```

## Adding a New Tool

Add a new `@tool` function in `Code/Servers/agents/tools/`:

```python
from agent_framework import tool

@tool
def my_tool(query: str) -> str:
    """Description of what this tool does."""
    # Your logic here
    return result
```

Register it in `Code/Servers/agents/providers/af_provider.py`.

## Architecture

```
┌─────────────────────────────────────┐
│  Frontend (React + Vite)            │
│  http://localhost:3010              │
├─────────────────────────────────────┤
│  Servers/agents (FastAPI)           │
│  Agent Framework orchestration      │
│  ├── agents/ (definitions)          │
│  ├── tools/ (@tool functions)       │
│  ├── workflows/ (orchestration)     │
│  └── DevUI (port 8090)              │
├─────────────────────────────────────┤
│  Servers/eval (FastAPI)             │
│  LLM response quality evaluation    │
├─────────────────────────────────────┤
│  Shared/ (cross-cutting)            │
│  middleware, clients, config, eval   │
├─────────────────────────────────────┤
│  Azure OpenAI · Azure Kusto · CosmosDB │
└─────────────────────────────────────┘
```
