import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { api } from "@/lib/api";

import { useAudience } from "./useBroadcast";
import { useUserAction, useUsers } from "./useUsers";

function wrapper(qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
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

  it("useAudience fetches the recipient count for the chosen languages", async () => {
    mock.onGet("/admin/broadcast/").reply(200, { recipients: 42 });
    const { result } = renderHook(() => useAudience(["fa", "en"]), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.recipients).toBe(42);
    // Comma-joined languages, and the two audience refinements always sent explicitly — the count
    // has to be computed the same way the send will be, so "unset" must not mean "server default".
    expect(mock.history.get[0].params).toEqual({
      languages: "fa,en",
      only_active: false,
      only_referrers: false,
    });
  });

  it("an action keeps the record dialog's detail instead of overwriting it with a row", async () => {
    // The action's reply is a list ROW. Written over ["user", id] it dropped `recent_claims`, the
    // dialog read `.length` off undefined, and the whole console fell to the error screen — after
    // the unban had already applied on the server.
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const claims = [{ location: "Germany", created_at: "2026-09-01T00:00:00Z" }];
    qc.setQueryData(["user", 5], {
      telegram_id: 5,
      status: "banned",
      recent_claims: claims,
      claims_series: [],
      traffic_bytes: null,
    });
    mock.onPost("/admin/users/5/unban").reply(200, { telegram_id: 5, status: "available" });
    mock.onGet("/admin/users/5/detail").reply(200, {
      telegram_id: 5,
      status: "available",
      recent_claims: claims,
      claims_series: [],
      traffic_bytes: null,
    });

    const { result } = renderHook(() => useUserAction(), { wrapper: wrapper(qc) });
    await act(() => result.current.mutateAsync({ id: 5, action: "unban" }));

    const detail = qc.getQueryData<{ status: string; recent_claims: unknown[] }>(["user", 5]);
    expect(detail?.status).toBe("available");
    expect(detail?.recent_claims).toEqual(claims);
  });
});
