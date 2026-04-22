/**
 * HTTP client for the Ratio Fuse decision-aware metrics API.
 *
 * In development the Vite dev server proxies `/fuse-api` → `http://127.0.0.1:8008`
 * (configured in vite.config.ts, with path rewrite stripping the prefix).
 */

import type {
  EvaluateScenarioRequest,
  EvaluateScenarioResponse,
  MockModeResponse,
  SafetyOptionsResponse,
  SafetyPromptRequest,
  SafetyPromptResponse,
  ScenariosResponse,
} from '../types/fuse';

const FUSE_PREFIX = '/fuse-api';

async function fuseFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${FUSE_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Fuse API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function listScenarios(): Promise<ScenariosResponse> {
  return fuseFetch<ScenariosResponse>('/v1/scenarios');
}

export function evaluateScenario(body: EvaluateScenarioRequest): Promise<EvaluateScenarioResponse> {
  return fuseFetch<EvaluateScenarioResponse>('/v1/scenarios/evaluate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getSafetyOptions(): Promise<SafetyOptionsResponse> {
  return fuseFetch<SafetyOptionsResponse>('/v1/safety/options');
}

export function generateSafetyPrompts(body: SafetyPromptRequest): Promise<SafetyPromptResponse> {
  return fuseFetch<SafetyPromptResponse>('/v1/safety/generate-prompts', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getMockMode(): Promise<MockModeResponse> {
  return fuseFetch<MockModeResponse>('/v1/config/mock-mode');
}

export function setMockMode(enabled: boolean): Promise<MockModeResponse> {
  return fuseFetch<MockModeResponse>('/v1/config/mock-mode', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  });
}
