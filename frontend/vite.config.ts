/**
 * Vite build config. React for components, Tailwind v4 via its Vite plugin (no PostCSS
 * config needed). The API base URL is NOT here: it comes from VITE_API_BASE_URL at build
 * time (see .env.example and src/api/client.ts).
 */
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true },
});
