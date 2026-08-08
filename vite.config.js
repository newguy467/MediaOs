import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Production UI pipeline
 * ----------------------
 * `npm run build` emits hashed JS/CSS into app/static/assets/ and writes
 * app/static/index.html (Vite-built). Legacy Babel CDN files (app.js) are
 * kept as fallback when VITE_UI=0 or dist assets are missing.
 *
 * emptyOutDir is false so we never wipe app/static/app.js, styles.css,
 * manifest, etc. Only index.html is overwritten by the build.
 */
export default defineConfig({
  plugins: [react()],
  root: "ui",
  base: "/",
  build: {
    outDir: path.resolve(__dirname, "app/static"),
    emptyOutDir: false,
    sourcemap: true,
    assetsDir: "assets",
    rollupOptions: {
      input: path.resolve(__dirname, "ui/index.html"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
