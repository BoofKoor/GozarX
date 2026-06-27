import { beforeEach, describe, expect, it } from "vitest";

import {
  clearAuth,
  getAccessToken,
  getRefreshToken,
  getUsername,
  isAuthenticated,
  setAccessToken,
  setTokens,
  setUsername,
} from "./auth";

describe("auth token storage", () => {
  beforeEach(() => localStorage.clear());

  it("stores and reads the token pair", () => {
    expect(isAuthenticated()).toBe(false);
    setTokens("acc", "ref");
    expect(getAccessToken()).toBe("acc");
    expect(getRefreshToken()).toBe("ref");
    expect(isAuthenticated()).toBe(true);
  });

  it("updates the access token alone", () => {
    setTokens("acc", "ref");
    setAccessToken("acc2");
    expect(getAccessToken()).toBe("acc2");
    expect(getRefreshToken()).toBe("ref");
  });

  it("stores the username and clears everything", () => {
    setTokens("acc", "ref");
    setUsername("root");
    expect(getUsername()).toBe("root");
    clearAuth();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(getUsername()).toBeNull();
  });
});
