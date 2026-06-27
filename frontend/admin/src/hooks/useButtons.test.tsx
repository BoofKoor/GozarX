import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { api } from "@/lib/api";

import { useButtons } from "./useButtons";
import { useTexts } from "./useTexts";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("button + text hooks", () => {
  let mock: MockAdapter;
  beforeEach(() => {
    mock = new MockAdapter(api);
  });
  afterEach(() => mock.restore());

  it("useButtons fetches the catalogue listing", async () => {
    mock.onGet("/admin/buttons/").reply(200, [{ key: "menu_config", screen: "main_menu" }]);
    const { result } = renderHook(() => useButtons(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].key).toBe("menu_config");
  });

  it("useTexts fetches the content keys", async () => {
    mock.onGet("/admin/texts/").reply(200, [{ key: "welcome", fa: "سلام", placeholders: [] }]);
    const { result } = renderHook(() => useTexts(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].key).toBe("welcome");
  });
});
