import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { api } from "@/lib/api";

import { SiteStats } from "./SiteStats";

let mock: MockAdapter;

const metric = (value: number, previous: number, change_pct: number | null) => ({
  value,
  previous,
  change_pct,
});

const series = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    day: `2026-07-${String(i + 1).padStart(2, "0")}`,
    count: i,
  }));

const STATS = {
  range_days: 14,
  visitors: metric(120, 80, 50),
  new_visitors: metric(90, 60, 50),
  returning_visitors: metric(30, 20, 50),
  claimers: metric(24, 30, -20),
  claims: metric(31, 40, -22.5),
  conversion_pct: 20,
  conversion_pct_prev: 37.5,
  location_changes: 4,
  total_devices_all_time: 9999,
  devices_claimed_all_time: 1200,
  conversion_all_time_pct: 12,
  active_configs_live: 7,
  active_configs_stale: 3,
  push_subscribers: 42,
  configs_today: 5,
  status_counts: { available: 10, active_config: 10 },
  claims_series: series(14),
  visitors_series: series(14),
  top_locations: [{ label: "Germany", count: 12 }],
  locations_total: 4,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/site/stats"]}>
        <SiteStats />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mock = new MockAdapter(api);
  mock.onGet("/admin/site/stats/analytics").reply(200, {
    range_days: 14,
    claims_in_range: 0,
    devices_active_in_range: 0,
    dau: 0,
    wau: 0,
    mau: 0,
    stickiness_pct: 0,
    visitors_24h: 0,
    visitors_7d: 0,
    visitors_30d: 0,
    visit_stickiness_pct: 0,
    reward_economy: [],
    streak_distribution: {},
    active_streaks: 0,
    push: { active: 0, inactive: 0, by_locale: [] },
    abuse: { top_ip_buckets: [], shared_fingerprint_devices: 0 },
  });
});
afterEach(() => mock.restore());

describe("SiteStats", () => {
  it("headlines the WINDOWED visitor count, not the all-time identity count", async () => {
    // The lifetime figure (9,999) used to be the headline under the word "visits". It is still
    // reported, but in its own card — the KPI has to be the one that moves with the range.
    mock.onGet("/admin/site/stats/").reply(200, STATS);
    renderPage();

    const card = (await screen.findByText(/^بازدیدکننده \(/)).closest("div")!.parentElement!;
    expect(card).toHaveTextContent("۱۲۰");
    expect(card).not.toHaveTextContent("۹٬۹۹۹");
  });

  it("shows each KPI against the previous, equal-length window", async () => {
    mock.onGet("/admin/site/stats/").reply(200, STATS);
    renderPage();
    expect(await screen.findByText(/دورهٔ قبل: ۸۰/)).toBeInTheDocument();
    // A fall in claimers must read as a fall, not as an unqualified number.
    expect(screen.getByText(/۲۰٪/, { selector: "span" })).toBeInTheDocument();
  });

  it("separates live active configs from ones the reconcile sweep hasn't caught up with", async () => {
    mock.onGet("/admin/site/stats/").reply(200, STATS);
    renderPage();
    expect(await screen.findByText("کانفیگ فعال (اکنون)")).toBeInTheDocument();
    expect(screen.getByText(/۳ مورد منقضی ولی هنوز هم‌گام‌نشده/)).toBeInTheDocument();
  });

  it("says how many locations the top-10 list is hiding", async () => {
    mock.onGet("/admin/site/stats/").reply(200, STATS);
    renderPage();
    // 4 distinct locations, 1 shown — a silent cap reads as "these are all of them".
    expect(await screen.findByText(/۳ لوکیشن دیگر نمایش داده نشده/)).toBeInTheDocument();
  });

  it("re-queries BOTH the funnel and the analytics band when the range changes", async () => {
    mock.onGet("/admin/site/stats/").reply(200, STATS);
    renderPage();
    await screen.findByText(/^بازدیدکننده \(/);

    await userEvent.click(screen.getByRole("radio", { name: "۳۰ روز" }));
    await waitFor(() => {
      const asked = mock.history.get.filter((r) => r.params?.days === 30).map((r) => r.url);
      expect(asked).toContain("/admin/site/stats/");
      expect(asked).toContain("/admin/site/stats/analytics");
    });
  });
});
