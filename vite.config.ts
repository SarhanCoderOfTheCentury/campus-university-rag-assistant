import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
    server: {
      allowedHosts: true,
      // Optional local FastAPI proxy. This does not enable a backend in production.
      proxy: env.RAG_DEV_API_ORIGIN ? { '/api': { target: env.RAG_DEV_API_ORIGIN, changeOrigin: true } } : undefined,
    },
  }
})
