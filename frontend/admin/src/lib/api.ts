// Axios client for the admin API.
//
// Request interceptor attaches `Authorization: Bearer <access>`. Response interceptor does a single
// refresh-then-retry on 401 (guarded so parallel 401s share one in-flight refresh); if refresh
// fails, it clears auth and bounces to /login. Same-origin in prod (nginx proxies /api/*); in dev,
// Vite proxies /api/* to the backend (see vite.config.ts).

import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

import { t } from "@/i18n";

import { clearAuth, getAccessToken, getRefreshToken, setTokens } from "./auth";

export const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing = false;
let waiters: ((token: string | null) => void)[] = [];

function notifyWaiters(token: string | null): void {
  waiters.forEach((cb) => cb(token));
  waiters = [];
}

function bounceToLogin(): void {
  clearAuth();
  // The panel is mounted under /admin/ (router basename), so the login route is /admin/login.
  if (window.location.pathname !== "/admin/login") {
    window.location.replace("/admin/login");
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    // Bare axios (not `api`) so this request skips the interceptors below.
    // The backend ROTATES the pair on every refresh (fresh access + fresh 7-day refresh); persist
    // both, or the refresh token stays frozen at login and the session dies 7 days later even while
    // the admin is active.
    const resp = await axios.post<{ access_token: string; refresh_token: string }>(
      "/api/admin/auth/refresh",
      { refresh_token: refreshToken },
    );
    setTokens(resp.data.access_token, resp.data.refresh_token);
    return resp.data.access_token;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const original = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;

    if (status !== 401 || !original) {
      return Promise.reject(error);
    }
    // Already retried with a fresh token and still 401 → give up.
    if (original._retry) {
      bounceToLogin();
      return Promise.reject(error);
    }
    original._retry = true;

    if (refreshing) {
      return new Promise((resolve, reject) => {
        waiters.push((token) => {
          if (!token) {
            reject(error);
            return;
          }
          original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
          resolve(api.request(original));
        });
      });
    }

    refreshing = true;
    const token = await refreshAccessToken();
    refreshing = false;
    notifyWaiters(token);

    if (!token) {
      bounceToLogin();
      return Promise.reject(error);
    }
    original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
    return api.request(original);
  },
);

/**
 * The server's own explanation of a failure, or `fallback`.
 *
 * The panel used to collapse every mutation error into one generic toast, so a 400 that said
 * exactly which location the squad doesn't serve, a 409 ("the squad matched no enabled host") and a
 * 502 ("panel unreachable") all read as "ذخیره نشد." — three different problems, one useless
 * message. FastAPI puts the reason in `detail`; surface it.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;
  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  // 422 bodies are a list of per-field errors; show the first message rather than "[object Object]".
  if (Array.isArray(detail)) {
    const first = detail.find((d) => typeof d?.msg === "string");
    if (first) return String(first.msg);
  }
  if (!error.response) return t("ui.offline");
  return fallback;
}
