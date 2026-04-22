# Skill: Add a New React Page

## When to Use

Use this skill when asked to add a new page or view to the React frontend, including routing, components, and API integration.

## Steps

### 1. Create the page component

Create `Code/Frontend/src/pages/<PageName>.tsx`:

```typescript
import { useState, useEffect } from "react";

interface <PageName>Props {
  // Define props if needed
}

export function <PageName>Page({}: <PageName>Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="page-container">
      <h1><Page Title></h1>
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      {/* Page content */}
    </div>
  );
}
```

### 2. Add API client functions (if needed)

Create or update `Code/Frontend/src/api/<feature>.ts`:

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface <Feature>Request {
  inputData: string;
}

export interface <Feature>Response {
  result: string;
  metadata?: Record<string, unknown>;
}

export async function fetch<Feature>(request: <Feature>Request): Promise<<Feature>Response> {
  const response = await fetch(`${API_BASE}/api/<feature>/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_data: request.inputData }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
```

### 3. Create a custom hook (if the page has complex state)

Create `Code/Frontend/src/hooks/use<Feature>.ts`:

```typescript
import { useState, useCallback } from "react";
import { fetch<Feature>, type <Feature>Response } from "../api/<feature>";

export function use<Feature>() {
  const [data, setData] = useState<<Feature>Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async (input: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetch<Feature>({ inputData: input });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, execute };
}
```

### 4. Add routing

Update `Code/Frontend/src/App.tsx`:

```typescript
import { <PageName>Page } from "./pages/<PageName>";

// Inside the router/switch:
<Route path="/<page-path>" element={<<PageName>Page />} />
```

### 5. Add types (if new shared types are needed)

Create or update `Code/Frontend/src/types/<feature>.ts`:

```typescript
export interface <Feature>Result {
  id: string;
  status: "pending" | "complete" | "error";
  data: Record<string, unknown>;
}
```

## Rules

- **Functional components only** — no class components
- **TypeScript strict mode** — avoid `any`; if unavoidable, add a `// TODO: type this` comment
- **Custom hooks** for data fetching and complex state — keep page components thin
- **API layer separation** — all fetch calls in `api/`, never call `fetch()` directly in components
- **No inline styles** — use CSS classes or CSS modules
- **Error handling** — wrap async calls in try/catch, show user-friendly error messages
- **Loading states** — always show loading indicators during async operations
- **Named exports** — use `export function` not `export default`
- **Props interfaces** — define explicit TypeScript interfaces for all component props
- **File naming** — `PascalCase.tsx` for components/pages, `camelCase.ts` for utils/api/hooks
