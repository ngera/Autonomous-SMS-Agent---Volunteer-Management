import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Browser → vite (5173) → uvicorn (127.0.0.1:8000). Keeps the
      // browser same-origin, so CORS, IPv6 vs IPv4 resolution, and
      // cookie semantics become irrelevant. Vite handles the loopback
      // hop on the IPv4 interface that uvicorn is actually bound to.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
