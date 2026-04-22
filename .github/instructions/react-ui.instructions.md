---
applyTo: Code/Frontend/**
---

# React UI Instructions

## Project Context
- React 18 + Vite + TypeScript frontend at `Code/Frontend/`
- Dev server: `npm run dev` → port 3010
- Production: Docker (nginx) → port 3000
- Communicates with backend at `http://localhost:8000`

## File Conventions

| Category | Location | Naming |
|----------|----------|--------|
| Pages | `src/pages/` | `PascalCase.tsx` |
| Components | `src/components/` | `PascalCase.tsx` |
| Hooks | `src/hooks/` | `use*.ts` |
| API clients | `src/api/` | `camelCase.ts` |
| Types | `src/types/` | `camelCase.ts` |
| Constants | `src/constants/` | `camelCase.ts` |

## Component Rules

- **Functional components only** — no class components
- **Named exports** — `export function MyComponent()`, never `export default`
- **Props interface** above every component:
  ```typescript
  interface MyComponentProps {
    title: string;
    onAction: () => void;
  }
  export function MyComponent({ title, onAction }: MyComponentProps) { ... }
  ```

## TypeScript Rules

- **Strict mode** — avoid `any`; use `unknown` and narrow types
- **Interface for objects** — `interface User { ... }` over `type User = { ... }`
- **Explicit return types** on exported functions
- **Utility types** — use `Pick<T, K>`, `Omit<T, K>`, `Partial<T>` over manual retyping

## Data Fetching

- **All fetch calls in `src/api/`** — components never call `fetch()` directly
- **Custom hooks** in `src/hooks/` for stateful data fetching
- **Always handle** loading, error, and success states
- **Type API responses** — define response interfaces in `src/types/`
- **Base URL** from `import.meta.env.VITE_API_BASE_URL`

## Styling

- **No inline styles** — use CSS modules or CSS classes
- **Consistent spacing** — use design tokens / CSS variables
- **Responsive** — test at mobile and desktop widths

## State Management

- **React hooks + context** for local and shared state
- **Custom hooks** to encapsulate complex state logic
- **No Redux** unless the team explicitly decides to adopt it
- **Server state** (API data) managed via custom hooks with loading/error/data pattern
