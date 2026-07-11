import type { NextConfig } from "next";

// The site is served behind nginx in production (`/` -> this app; `/api` -> the FastAPI backend).
// In local dev we proxy `/api/*` to the backend so the browser talks to one origin (cookies work).
const BACKEND = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server bundle for the Docker image (P10)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};

export default nextConfig;
