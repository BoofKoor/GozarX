// Typed client for the public backend API (/api/public/*). All calls are device-scoped, so they run
// in the BROWSER with credentials included — the signed httpOnly device cookie round-trips naturally
// (no SSR set-cookie dance). Same-origin in prod (nginx); proxied by next.config rewrites in dev.

const BASE = "/api/public";

export interface StatusResponse {
  status: string;
  active: boolean;
  has_config: boolean;
  live: boolean;
  data_exhausted: boolean;
  daily_limit: string;
  daily_limit_bytes: number;
  usage: string;
  usage_bytes: number;
  remaining: string;
  cooldown: string;
  can_claim: boolean;
  configs: number;
  referral_count: number;
  referral_cap: number;
  streak_count: number;
  streak_days: number;
  location: string | null;
  link: string | null;
  ref_code: string;
}

export interface ClaimResponse {
  ok: boolean;
  reason?: string | null;
  location?: string | null;
  link?: string | null;
  expires?: string | null;
  size?: string | null;
  changed: boolean;
  retry_after?: string | null;
}

export interface RewardResponse {
  ok: boolean;
  reason?: string | null;
  reward_type?: string | null;
  amount_mb?: number | null;
  streak_count?: number | null;
  streak_active: boolean;
  new_daily?: string | null;
}

export interface TransferCreateResponse {
  ok: boolean;
  reason?: string | null;
  code?: string | null;
  expires_in?: number | null;
}

export interface RedeemResponse {
  ok: boolean;
  reason?: string | null;
  has_config: boolean;
  referral_count: number;
}

export interface PublicConfig {
  turnstile_site_key: string;
  vapid_public_key: string;
  turnstile_enabled: boolean;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include", cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    // 5xx: a real server error → throw so the caller shows a retryable failure.
    if (res.status >= 500) throw new ApiError(res.status, path);
    // 4xx security guards (429 rate-limited / 403 turnstile_failed) come back as {detail: "..."}.
    // Surface that as {ok:false, reason} so callers render the SAME state screens as domain 200s
    // instead of a misleading generic error.
    return {
      ok: false,
      reason: typeof data.detail === "string" ? data.detail : `http_${res.status}`,
    } as T;
  }
  return data as T;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public path: string,
  ) {
    super(`api ${status} ${path}`);
  }
}

export const api = {
  config: () => get<PublicConfig>("/config"),
  status: () => get<StatusResponse>("/status"),
  locations: () => get<{ locations: string[] }>("/locations"),
  claim: (location: string, turnstileToken?: string) =>
    post<ClaimResponse>("/claim", { location, turnstile_token: turnstileToken }),
  claimReward: (reward_type: "pwa" | "push" | "streak") =>
    post<RewardResponse>("/rewards/claim", { reward_type }),
  createTransfer: () => post<TransferCreateResponse>("/transfer/create"),
  redeemTransfer: (code: string) => post<RedeemResponse>("/transfer/redeem", { code }),
  resetDevice: () => post<{ ok: boolean }>("/device/reset"),
  contact: (body: {
    subject?: string;
    body: string;
    reply_handle?: string;
    locale: string;
    turnstile_token?: string;
  }) => post<{ ok: boolean; reason?: string | null }>("/contact", body),
  subscribePush: (sub: { endpoint: string; p256dh: string; auth: string; locale: string }) =>
    post<{ ok: boolean }>("/push/subscribe", sub),
  unsubscribePush: (endpoint: string) => post<{ ok: boolean }>("/push/unsubscribe", { endpoint }),
};
