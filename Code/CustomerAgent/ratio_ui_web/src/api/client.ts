/**
 * HTTP client for the Ratio AI backend API.
 *
 * In development the Vite dev server proxies `/api` → `http://127.0.0.1:8000`
 * (configured in vite.config.ts).  In production the same relative path is
 * served by the reverse proxy / nginx in front of the React app, so no
 * environment variable or hardcoded host is needed.
 */
const API_PREFIX = '/api';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}
