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
});
