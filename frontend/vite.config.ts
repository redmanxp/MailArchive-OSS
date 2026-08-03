import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    host: true,
    proxy: {
      "/api": "http://127.0.0.1:18100",
      "/health": "http://127.0.0.1:18100",
    },
  },
  preview: {
    port: 5175,
    host: true,
    strictPort: true,
  },
});
