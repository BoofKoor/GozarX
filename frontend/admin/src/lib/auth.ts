// Auth token storage. Single-admin panel over TLS → the JWT pair lives in localStorage; the axios
// interceptor (api.ts) refreshes the access token before logging out. Username is cached for the
// top bar; it's re-fetched from /auth/me when needed.

const ACCESS_KEY = "gozarx_admin_access";
const REFRESH_KEY = "gozarx_admin_refresh";
const USER_KEY = "gozarx_admin_user";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function getUsername(): string | null {
  return localStorage.getItem(USER_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function setAccessToken(access: string): void {
  localStorage.setItem(ACCESS_KEY, access);
}

export function setUsername(username: string): void {
  localStorage.setItem(USER_KEY, username);
}

export function clearAuth(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}
