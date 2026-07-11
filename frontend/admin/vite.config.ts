/// <reference types="vitest/config" />
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  // The admin panel is served under /admin/ (the website owns the domain root). Vite prefixes all
  // built asset URLs with this base; the router uses a matching basename (see main.tsx).
  base: "/admin/",
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      // Smaller initial chunks (panel is used over slow connections).
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          query: ["@tanstack/react-query", "axios"],
        },
      },
    },
  },
  server: {
    port: 5173,
    // `npm run dev`: proxy /api/* to the local FastAPI backend (no CORS hassle).
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
