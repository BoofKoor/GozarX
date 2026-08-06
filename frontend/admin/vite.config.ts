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
        // A function, not the object form. `{ charts: ["recharts"] }` gave recharts its own chunk
        // but left `components/charts/primitives` — a recharts wrapper shared by the dashboard, the
        // system page and the website stats — to Rollup's shared-code hoisting, which put it in the
        // ENTRY. So `index.html` carried a `modulepreload` for the 424 KB charts chunk and every
        // route paid for it, including `/login`. Naming the wrappers keeps the whole recharts graph
        // behind the lazy routes that use it.
        manualChunks(id) {
          if (id.includes("node_modules")) {
            // `clsx` before `charts`: recharts depends on it too, and left unpinned Rollup
            // deduplicated the single copy INTO the recharts chunk — so the entry, which uses
            // `clsx` in almost every component, imported 434 KB of charting to get a 400-byte
            // string joiner. That one edge is what kept `/login` paying for recharts.
            if (/node_modules\/(clsx|sonner)\//.test(id)) return "core";
            if (/node_modules\/(recharts|victory-vendor|d3-)/.test(id)) return "charts";
            if (/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler)\//.test(id))
              return "react";
            if (/node_modules\/(@tanstack|axios)\//.test(id)) return "query";
            return undefined;
          }
          // Our own recharts-facing modules get their OWN name rather than joining the vendor
          // chunk. Merged into `charts`, Rollup followed `primitives`' own `@/i18n` import and
          // pulled the whole message catalogue in after it — so every route, `/login` included,
          // needed the 511 KB chart bundle to render a single string. Named separately, the
          // catalogue stays in the entry (which also needs it) and this chunk imports both.
          //
          // The hand-drawn SVG charts are deliberately NOT here: they have no recharts dependency,
          // and pulling them in would drag it back to the dashboard overview — the one screen that
          // never renders a recharts chart.
          if (/src\/components\/charts\/primitives|src\/lib\/chartTheme/.test(id)) return "chartkit";
          // Pin the core every chunk needs. Left unnamed, Rollup is free to park the message
          // catalogue inside whichever chunk happens to import it — it chose `chartkit`, which put
          // the entry back on a static path to recharts and undid the split. Named, it is its own
          // chunk and both the entry and the chart code import it.
          if (/src\/(i18n|lib\/format|lib\/api|lib\/auth)/.test(id)) return "core";
          return undefined;
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
