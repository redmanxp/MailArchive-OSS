import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages project site: https://redmanxp.github.io/MailArchive-OSS/
const base = process.env.VITE_BASE || "/MailArchive-OSS/";

export default defineConfig({
  plugins: [react()],
  base,
});
