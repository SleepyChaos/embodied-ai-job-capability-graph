import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const port = 5000;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port,
    strictPort: false,
    host: "0.0.0.0",
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    port,
    strictPort: false,
    host: "0.0.0.0",
  },
});
