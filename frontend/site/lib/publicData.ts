// Server-side reads of the two DEVICE-INDEPENDENT public endpoints (/config, /stats), for figures the
// homepage renders into its HTML — the hero's "fresh every Nh" and "N+ configs delivered" chips. Same
// pattern as lib/siteCopy: BACKEND_ORIGIN direct, ISR-revalidated, and null on any failure, so the
// caller hides the figure instead of printing a guess. Never /status from here: reading it mints a
// device, and a server render must not.

import type { PublicConfig, PublicStats } from "@/lib/api";

const BACKEND = (process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const REVALIDATE = 300;

async function read<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BACKEND}/api/public${path}`, { next: { revalidate: REVALIDATE } });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchPublicConfig = () => read<PublicConfig>("/config");
export const fetchPublicStats = () => read<PublicStats>("/stats");
