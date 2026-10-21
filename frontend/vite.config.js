import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In production FastAPI serves the built files under /app/ (the backend reserves that word).
// In development Vite serves the page and proxies API calls to uvicorn, so the browser sees
// ONE origin and CORS never comes up.
const API = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "../app/static/app",  // straight into the Python package, where FastAPI will serve it
    emptyOutDir: true,            // required when outDir is outside the project root
  },
  server: {
    proxy: {
      "/health": API,
      "/auth": API,
      "/shorten": API,
      "/urls": API,
      // keys starting with ^ are regular expressions: /<code>/analytics and /<code>/analytics/summary
      "^/[A-Za-z0-9_-]+/analytics(/summary)?$": API,
            // any single-segment path, e.g. DELETE /Ab3xYz (but not /app, which belongs to Vite)
      "^/(?!app$)[A-Za-z0-9_-]+$": API,
    },
  },
});