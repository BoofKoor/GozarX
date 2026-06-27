import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { api } from "@/lib/api";

import { useAudience } from "./useBroadcast";
import { useUsers } from "./useUsers";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("users + broadcast hooks", () => {
  let mock: MockAdapter;
  beforeEach(() => {
    mock = new MockAdapter(api);
  });
  afterEach(() => mock.restore());

  it("useUsers fetches a page", async () => {
    mock.onGet("/admin/users/").reply(200, {
      items: [{ telegram_id: 1001, status: "available" }],
      total: 1,
      page: 1,
      page_size: 25,
    });
    const { result } = renderHook(() => useUsers({ page: 1 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0].telegram_id).toBe(1001);
    expect(result.current.data?.total).toBe(1);
  });

  it("useAudience fetches the recipient count", async () => {
    mock.onGet("/admin/broadcast/").reply(200, { recipients: 42 });
    const { result } = renderHook(() => useAudience(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.recipients).toBe(42);
  });
});
