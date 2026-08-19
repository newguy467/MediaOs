import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  root: "ui",
  publicDir: "public",
  build: {
    outDir: path.resolve(__dirname, "app/static"),
    emptyOutDir: true,
    sourcemap: true,
    assetsDir: "assets",
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/logo": "http://127.0.0.1:8000",
    },
  },
});
