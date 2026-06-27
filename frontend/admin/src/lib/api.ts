// Axios client for the admin API.
//
// Request interceptor attaches `Authorization: Bearer <access>`. Response interceptor does a single
// refresh-then-retry on 401 (guarded so parallel 401s share one in-flight refresh); if refresh
// fails, it clears auth and bounces to /login. Same-origin in prod (nginx proxies /api/*); in dev,
// Vite proxies /api/* to the backend (see vite.config.ts).

import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

import { clearAuth, getAccessToken, getRefreshToken, setAccessToken } from "./auth";

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
  if (window.location.pathname !== "/login") {
    window.location.replace("/login");
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    // Bare axios (not `api`) so this request skips the interceptors below.
    const resp = await axios.post<{ access_token: string }>("/api/admin/auth/refresh", {
      refresh_token: refreshToken,
    });
    setAccessToken(resp.data.access_token);
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
