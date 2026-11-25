/**
 * Vite build config. React for components, Tailwind v4 via its Vite plugin (no PostCSS
 * config needed).
 *
 * In production the website and the API share one domain: Vercel sends /api/* to the
 * FastAPI service (root vercel.json). The dev proxy below copies that locally: the browser
 * calls /api/v1/... on port 5173 and Vite forwards it to uvicorn on port 8000.
 */
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://localhost:8000" },
  },
});
