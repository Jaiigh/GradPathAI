// Thin client for the GradPath API (gradpath/api/app.py). Vite proxies /api to 127.0.0.1:8000 in development.
async function call(path, options = {}) {
  const form = options.body instanceof FormData;
  const res = await fetch(`/api${path}`, {
    headers: form ? {} : { 'Content-Type': 'application/json' },
    ...options,
    body: form ? options.body : options.body ? JSON.stringify(options.body) : undefined
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
  upload: (file, sessionId) => {
    const body = new FormData();
    body.append('file', file);
    return call(sessionId ? `/sessions/${sessionId}/report` : '/uploads', { method: 'POST', body });
  },
  get: (id, operator) => call(`/sessions/${id}${operator ? '?operator=true' : ''}`),
  message: (id, text) => call(`/sessions/${id}/messages`, { method: 'POST', body: { text } }),
  record: (id, resolve, confirm = true, profile) => call(`/sessions/${id}/record`, { method: 'POST', body: { resolve, confirm, profile } }),
  internship: (id, completed) => call(`/sessions/${id}/internship`, { method: 'POST', body: { completed } }),
  goal: (id, card_id, approve) => call(`/sessions/${id}/goal`, { method: 'POST', body: { card_id, approve } }),
  blocker: (id, card_id, choose, decline = false) => call(`/sessions/${id}/blocker`, { method: 'POST', body: { card_id, choose, decline } })
};
