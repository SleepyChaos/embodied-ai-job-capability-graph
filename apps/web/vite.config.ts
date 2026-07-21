import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {},
  },
  server: {
    host: "0.0.0.0",
    port: Number(process.env.DEPLOY_RUN_PORT) || 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
