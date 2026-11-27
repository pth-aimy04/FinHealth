import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
const apiOrigin = process.env.FINHEALTH_API_ORIGIN ?? "http://127.0.0.1:8000";

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  base: command === "serve" ? "/" : "/static/",
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiOrigin,
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (request) => {
            // Preserve backend origin validation with the same-origin development proxy.
            request.setHeader("Origin", apiOrigin);
          });
        },
      },
    },
  },
  build: { chunkSizeWarningLimit: 750 },
}));
