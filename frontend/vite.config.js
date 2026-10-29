import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server forwards /api (HTTP + WebSocket) and /ws (call audio) to the
// FastAPI backend, so the browser never talks to Gemini and never sees the API key.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5190,
    strictPort: true,
    proxy: {
      "/api": { target: "http://localhost:8020", changeOrigin: true, ws: true },
      "/ws": { target: "ws://localhost:8020", ws: true },
    },
  },
});
