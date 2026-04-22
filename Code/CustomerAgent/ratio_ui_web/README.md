# Ratio AI — React Frontend

> **Port 3010 (dev) / 3000 (Docker)** · Production React web application published to Azure

The production-grade frontend for the RatioAI platform, built with React 18, TypeScript, and Vite. This is the user-facing application that is deployed to Azure.

---

## Quick Start

```bash
cd src/ratio_ui_web
npm install
npm run dev        # http://localhost:3010
```

Open http://localhost:3010 to view the application.

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Framework | React 18 |
| Language | TypeScript 5.5 (strict mode) |
| Build Tool | Vite 5.4 |
| Routing | React Router DOM v6 |
| HTTP Client | Fetch API via `apiFetch()` utility |
| Production Server | Nginx (Docker) |

### API Proxy

In development, the Vite dev server proxies requests as follows:

- `/api/*` → ratio-agents backend
- `/sr-api/*` → ratio-sr-insights backend
- `/fuse-api/*` → ratio-fuse backend
- `/customer-agent-api/*` → ratio-customer-health backend (`http://127.0.0.1:8020`)

Example for the main backend:

```
Browser → localhost:3010/api/* → Vite proxy → localhost:8000/api/*
```

In production, Nginx handles the same proxy pattern:

```
Browser → nginx:80/api/* → ratio-agents:8000/api/*
```

---

## Folder Structure

```
src/
├── api/          # HTTP client layer (apiFetch utility)
├── components/   # Reusable UI components (barrel export)
├── constants/    # App-wide constants and configuration values
├── hooks/        # Custom React hooks (barrel export)
├── pages/        # Route-level page components
│   └── customer-agent/  # Customer Agent (CHA) page components
└── types/        # Shared TypeScript type definitions
```

### Key Files

| File | Purpose |
|------|---------|
| `src/main.tsx` | ReactDOM entry point |
| `src/App.tsx` | React Router configuration |
| `src/api/client.ts` | Generic `apiFetch<T>()` HTTP client |
| `src/pages/HomePage.tsx` | Landing page component |
| `vite.config.ts` | Dev server and proxy configuration |
| `nginx.conf` | Production reverse proxy and SPA routing |
| `Dockerfile` | Multi-stage build (Node → Nginx Alpine) |

### Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `HomePage` | Landing page |
| `/customer-agent` | `ChaHomePage` | CHA Home |
| `/customer-agent/scenarios` | `ChaScenariosPage` | Simulation Scenarios |
| `/customer-agent/active` | `ChaActivePage` | Active Investigation with SSE |
| `/customer-agent/history` | `ChaHistoryPage` | Investigation History |
| `/customer-agent/agents` | `ChaAgentsPage` | Agent Registry |
| `/customer-agent/config` | `ChaConfigPage` | Configuration (8 tabs) |
| `/customer-agent/data` | `ChaDataPage` | Data Files browser |
| `/customer-agent/knowledge` | `ChaKnowledgePage` | Knowledge Base viewer |

---

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start Vite dev server on port 3010 |
| `npm run build` | Type-check and build for production |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint checks |

---

## Docker

```bash
cd src/ratio_ui_web
docker build -t ratio-ui-web:local .
docker run -p 80:80 ratio-ui-web:local
```

The Docker image uses a multi-stage build:
1. **Builder stage** — Node 20 Alpine builds the React app
2. **Runtime stage** — Nginx 1.27 Alpine serves static files with SPA fallback

---

## Configuration

No environment variables are required. The API base URL is always `/api` (relative path), handled by the proxy layer (Vite in dev, Nginx in production).

---

## Relationship to Streamlit UI

Both `ratio_ui_web` (React) and `ratio_ui_streamlit` (Streamlit) consume the **same backend APIs**. New features are prototyped in Streamlit first, then promoted to the production React app once validated.
