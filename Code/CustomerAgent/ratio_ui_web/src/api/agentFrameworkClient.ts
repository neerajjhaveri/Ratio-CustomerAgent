/**
 * API client for the Agent Framework endpoints on ratio-agents (port 8000).
 *
 * All paths go through the `/api` prefix which Vite proxies to
 * http://127.0.0.1:8000 in dev mode.
 */

const API_PREFIX = '/api/af';

async function afFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`AF API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/* ── Types ─────────────────────────────────────────────────── */

export interface AFAgentInfo {
  name: string;
  instructions: string;
  tools: string[];
}

export interface AFAgentsResponse {
  agents: AFAgentInfo[];
}

export interface AFConfigResponse {
  provider: string;
  available_providers: string[];
  agent_framework_available: boolean;
}

export interface AFChatResponse {
  agent: string;
  session_id: string | null;
  response: string;
}

/* ── Endpoints ─────────────────────────────────────────────── */

export function getAFConfig(): Promise<AFConfigResponse> {
  return afFetch('/config');
}

export function listAFAgents(): Promise<AFAgentsResponse> {
  return afFetch('/agents');
}

export function chatWithAgent(body: {
  agent_name?: string;
  message: string;
  session_id?: string;
}): Promise<AFChatResponse> {
  return afFetch('/chat', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Stream a chat response via Server-Sent Events.
 * Returns an async generator of text chunks.
 */
export async function* streamChatWithAgent(body: {
  agent_name?: string;
  message: string;
  session_id?: string;
}): AsyncGenerator<string, void, unknown> {
  const res = await fetch(`${API_PREFIX}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`AF Stream ${res.status}: ${text}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') return;
        try {
          const parsed = JSON.parse(payload);
          if (parsed.text) yield parsed.text;
          if (parsed.error) throw new Error(parsed.error);
        } catch {
          // skip unparseable lines
        }
      }
    }
  }
}
