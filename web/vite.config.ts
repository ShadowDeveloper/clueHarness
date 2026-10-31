import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` proxies API + WS to the FastAPI server (clue web --dev-origin http://localhost:5173).
// Build: bundle goes straight into the Python package so `clue web` serves it with no node at runtime.
// Pages: `npm run build:pages` produces a fully static bundle (analyst only, client-side solver) in
// web/dist for GitHub Pages; base/outDir come from the CLI flags set in that script.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../clue/web/static", emptyOutDir: true, sourcemap: false },
  server: {
    host: "0.0.0.0",
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test-setup.ts"] },
});
