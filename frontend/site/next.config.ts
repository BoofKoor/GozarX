import type { NextConfig } from "next";

// The site is served behind nginx in production (`/` -> this app; `/api` -> the FastAPI backend).
// In local dev we proxy `/api/*` to the backend so the browser talks to one origin (cookies work).
const BACKEND = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server bundle for the Docker image (P10)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
  async headers() {
    return [
      {
        // The pages are prerendered and cached INSIDE this server (C-61), and Next would advertise
        // that as `s-maxage=300` — an invitation to any shared cache (a Cloudflare "cache
        // everything" rule, say) to keep a copy. But one URL serves either language, picked per
        // request by `proxy.ts` (decision D3), so a shared copy would hand one visitor's language to
        // the next. `private` keeps them out; `no-cache` has the browser revalidate, which the ETag
        // answers with a 304 while the page is unchanged. Next honours a Cache-Control set here.
        // Same page set as the proxy's matcher: not Next's assets, not the API, not a file.
        source: "/((?!_next/|api/|[^?]*\\.[^/?]+$).*)",
        headers: [{ key: "Cache-Control", value: "private, no-cache" }],
      },
    ];
  },
  // No page uses next/image — flags, icons and the map are plain <img> of files already sized for
  // the page — yet `/_next/image` answered any request for a local image by resizing it with sharp.
  // An endpoint nothing needs is attack surface only, and it was that surface in several Next
  // advisories (an AVIF decoder RCE, an SVG DoS, an SSRF). Off, it is a 404.
  images: { unoptimized: true },
  experimental: {
    // A path no route claims gets app/global-not-found.tsx, drawn on the server — the root layout
    // sits inside `[lang]`, so there is no app-wide layout for an ordinary not-found to render in.
    globalNotFound: true,
    // Keep rendered pages in the bounded in-memory cache only. On disk, every path a visitor or a
    // scanner invents under a dynamic segment (`/l/<anything>`) left ~100 KB of cached 404 behind,
    // with nothing ever removing it; in memory the least recently used entry simply goes.
    isrFlushToDisk: false,
  },
};

export default nextConfig;
