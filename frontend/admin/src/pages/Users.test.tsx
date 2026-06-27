import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useUsers } from "@/hooks/useUsers";

import { Users } from "./Users";

vi.mock("@/hooks/useUsers", () => ({
  useUsers: vi.fn(),
  useUser: vi.fn(() => ({ data: undefined, isLoading: false })),
  useUserAction: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
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
  });
});
