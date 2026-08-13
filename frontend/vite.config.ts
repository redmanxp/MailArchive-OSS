import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const devApi = process.env.MAILARCHIVE_DEV_API || "http://127.0.0.1:18100";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    host: true,
    proxy: {
      "/api": devApi,
      "/health": devApi,
    },
  },
  preview: {
    port: 5175,
    host: true,
    strictPort: true,
  },
});
