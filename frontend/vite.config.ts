import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/analyze": { target: "http://localhost:8000", changeOrigin: true },
      "/status": { target: "http://localhost:8000", changeOrigin: true },
      "/result": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
