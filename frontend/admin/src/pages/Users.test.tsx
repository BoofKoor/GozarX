import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { useUsers } from "@/hooks/useUsers";

import { Users } from "./Users";

vi.mock("@/hooks/useUsers", () => ({
  useUsers: vi.fn(),
  useUser: vi.fn(() => ({ data: undefined, isLoading: false })),
  useUserAction: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useClaimedLocations: vi.fn(() => ({ data: ["Germany", "Finland"] })),
  downloadUsersCsv: vi.fn(),
}));

describe("Users", () => {
  it("renders a user row with a localized status badge", () => {
    vi.mocked(useUsers).mockReturnValue({
      data: {
        items: [
          {
            telegram_id: 1001,
            status: "banned",
            language: "fa",
            referral_count: 2,
            panel_username: null,
            reminder_enabled: true,
            referred_by: null,
            created_at: "2026-06-01T00:00:00Z",
            configs: null,
            last_location: "Germany",
          },
        ],
        total: 1,
        page: 1,
        page_size: 25,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof useUsers>);

    render(<Users />);
    expect(screen.getByText("1001")).toBeInTheDocument();
    // The badge is a <span> (the "مسدود" filter chip is a <button>).
    expect(screen.getByText("مسدود", { selector: "span" })).toBeInTheDocument();
    // The location column shows the user's LATEST claim, and the filter offers what was claimed.
    expect(screen.getByText("Germany", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Finland" })).toBeInTheDocument();
  });

  it("says the server is unreachable when offline, not that nobody has used the bot", () => {
    // A paused query (the browser is offline) is neither loading nor an error; it fell through to
    // the empty state, which is a claim about the bot's users.
    vi.mocked(useUsers).mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      fetchStatus: "paused",
    } as unknown as ReturnType<typeof useUsers>);
    render(<Users />);
    expect(screen.getByText("ارتباط با سرور برقرار نشد.")).toBeInTheDocument();
    expect(screen.queryByText("کاربری یافت نشد")).not.toBeInTheDocument();
  });

  it("asks for page 1 in the SAME render that changes a filter", async () => {
    // Reset in an effect, the page ran one render late and the list first fetched the old page
    // number under the new filter.
    vi.mocked(useUsers).mockClear();
    vi.mocked(useUsers).mockReturnValue({
      data: { items: [], total: 75, page: 1, page_size: 25 },
      isPending: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useUsers>);
    render(<Users />);
    await userEvent.click(screen.getByRole("button", { name: "صفحهٔ بعد" }));
    expect(vi.mocked(useUsers).mock.lastCall?.[0].page).toBe(2);
    await userEvent.click(screen.getByRole("radio", { name: "مسدود" }));
    const params = vi.mocked(useUsers).mock.calls.map((c) => c[0]);
    expect(params.some((p) => p.status === "banned" && p.page !== 1)).toBe(false);
    expect(params.at(-1)).toMatchObject({ status: "banned", page: 1 });
  });

  it("searches once the typing stops, not once per keystroke", async () => {
    vi.mocked(useUsers).mockClear();
    vi.mocked(useUsers).mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25 },
      isPending: false,
      isError: false,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useUsers>);
    render(<Users />);
    await userEvent.type(screen.getByRole("textbox", { name: /جستجو/ }), "73148");
    await waitFor(() => expect(vi.mocked(useUsers).mock.lastCall?.[0].search).toBe("73148"));
    const searched = new Set(vi.mocked(useUsers).mock.calls.map((c) => c[0].search));
    // Never the half-typed prefixes — each of those was a list request and a count query.
    expect(searched.has("7")).toBe(false);
    expect(searched.has("7314")).toBe(false);
  });
});
