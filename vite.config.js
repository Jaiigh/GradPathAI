import { defineConfig } from 'vite';

// The API runs on 127.0.0.1:8000 (python -m gradpath.api); the dev server proxies /api to it.
export default defineConfig({
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } }
});
