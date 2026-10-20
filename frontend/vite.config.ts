import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the backend only over HTTP. During development, Vite
// proxies /api to the FastAPI server so there is no CORS friction and no
// backend URL is baked into the client bundle.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
