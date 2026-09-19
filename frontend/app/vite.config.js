import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The client is served from the same origin as the API in both environments:
// here Vite proxies /api to Django, in production WhiteNoise serves this build
// beside it. That keeps the session cookie first-party, so there is no CORS to
// configure and no token for JavaScript to hold.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/admin': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
