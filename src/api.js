// Thin client for the GradPath API (gradpath/api/app.py). Vite proxies /api to 127.0.0.1:8000 in development.
async function call(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status}`);
  return data;
}

export const api = {
  health: () => call('/health'),
  personas: () => call('/personas'),
  tasks: () => call('/tasks'),
  create: (body) => call('/sessions', { method: 'POST', body }),
  get: (id, operator) => call(`/sessions/${id}${operator ? '?operator=true' : ''}`),
  message: (id, text) => call(`/sessions/${id}/messages`, { method: 'POST', body: { text } }),
  record: (id, resolve, confirm = true) => call(`/sessions/${id}/record`, { method: 'POST', body: { resolve, confirm } }),
  goal: (id, card_id, approve) => call(`/sessions/${id}/goal`, { method: 'POST', body: { card_id, approve } }),
  blocker: (id, card_id, choose, decline = false) => call(`/sessions/${id}/blocker`, { method: 'POST', body: { card_id, choose, decline } })
};
