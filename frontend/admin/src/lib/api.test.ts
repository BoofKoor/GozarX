import axios from "axios";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { api } from "./api";
import { getAccessToken, getRefreshToken, setTokens } from "./auth";

describe("api refresh-on-401 interceptor", () => {
  let mockApi: MockAdapter;
  let mockAxios: MockAdapter;

  beforeEach(() => {
    localStorage.clear();
    mockApi = new MockAdapter(api);
    mockAxios = new MockAdapter(axios); // the bare-axios refresh call
  });

  afterEach(() => {
    mockApi.restore();
    mockAxios.restore();
  });

  it("refreshes the access token on a 401 and retries the original request", async () => {
    setTokens("old-access", "the-refresh");
    let attempts = 0;
    mockApi.onGet("/admin/dashboard/stats").reply((config) => {
      attempts += 1;
      const auth = (config.headers as Record<string, unknown> | undefined)?.Authorization;
      return auth === "Bearer new-access" ? [200, { ok: true }] : [401, {}];
    });
    mockAxios
      .onPost("/api/admin/auth/refresh")
      .reply(200, { access_token: "new-access", refresh_token: "new-refresh" });

    const resp = await api.get("/admin/dashboard/stats");

    expect(resp.status).toBe(200);
    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("new-refresh"); // the rotated refresh token is persisted
    expect(attempts).toBe(2); // original 401 + the retry with the fresh token
  });

  it("passes a 401 from the AUTH routes straight through, keeping the stored session", async () => {
    // A wrong password on /login is the answer, not an expired token. Treated as one, it
    // "refreshed", retried the login, failed again and wiped the session still stored.
    setTokens("stored-access", "stored-refresh");
    let refreshed = false;
    mockApi.onPost("/admin/auth/login").reply(401, { detail: "invalid credentials" });
    mockAxios.onPost("/api/admin/auth/refresh").reply(() => {
      refreshed = true;
      return [200, { access_token: "x", refresh_token: "y" }];
    });

    await expect(api.post("/admin/auth/login", { username: "a", password: "b" })).rejects.toThrow();
    expect(refreshed).toBe(false);
    expect(getAccessToken()).toBe("stored-access");
    expect(getRefreshToken()).toBe("stored-refresh");
  });

  it("gives up on a refresh that never answers instead of queueing every request behind it", async () => {
    setTokens("old-access", "the-refresh");
    mockApi.onGet("/admin/users/").reply(401, {});
    mockAxios.onPost("/api/admin/auth/refresh").timeout();

    await expect(api.get("/admin/users/")).rejects.toThrow();
    // A second 401 afterwards is not stuck behind a `refreshing` flag left set.
    mockAxios.onPost("/api/admin/auth/refresh").reply(200, {
      access_token: "fresh",
      refresh_token: "fresh-r",
    });
    mockApi.onGet("/admin/texts/").reply((config) => {
      const auth = (config.headers as Record<string, unknown> | undefined)?.Authorization;
      return auth === "Bearer fresh" ? [200, []] : [401, {}];
    });
    setTokens("old-access", "the-refresh");
    await expect(api.get("/admin/texts/")).resolves.toMatchObject({ status: 200 });
  });
});
