import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Separate app from the public site on purpose: a data-dense admin
// dashboard (tables, forms, charts) has no reason to ship inside the
// public marketing bundle, and the two are unlikely to ever need the
// same deploy cadence. See ../PASS7_NOTES.md for the reasoning and the
// production-serving note (this needs its own path/subdomain fronted
// by the same origin as the backend, same caveat as Pass 3's uploads).
export default defineConfig({
  plugins: [react()],
  base: "./",

  server: {
    port: 5174,
    strictPort: false,
    open: false,
    proxy: {
      "/admin/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("error", () => {});
        },
      },
      "/uploads": {
        target: "http://localhost:8001",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("error", () => {});
        },
      },
    },
  },

  preview: {
    port: 4174,
    strictPort: false,
  },
});
