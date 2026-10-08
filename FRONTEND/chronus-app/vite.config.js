import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Forward /api/* to the CHRONUS FastAPI server (CHRONUS/api_server.py) so the
// browser only ever talks to this origin. The backend then needs no CORS,
// which keeps other websites from calling it. 127.0.0.1, not "localhost":
// the backend binds IPv4 loopback and Node may resolve localhost to ::1.
const api = {
  '/api': {
    target: 'http://127.0.0.1:8001',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}

export default defineConfig({
  plugins: [react()],
  server: { port: 3000, proxy: api },
  preview: { proxy: api },
  // Unit tests (npm test): src/**/*.test.js(x), in a simulated browser
  test: { environment: 'happy-dom', include: ['src/**/*.test.{js,jsx}'] },
})
