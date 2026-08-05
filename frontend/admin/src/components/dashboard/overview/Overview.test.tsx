import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/i18n";
import type { DashboardAnalytics, DashboardStats, Retention } from "@/types/api";

import { Overview } from "./Overview";

/** 2026-08-01 is a Saturday, so the seven days run Sat → Fri. */
const DAYS = [
  "2026-08-01",
  "2026-08-02",
  "2026-08-03",
  "2026-08-04",
  "2026-08-05",
  "2026-08-06",
  "2026-08-07",
];

const stats = (over: Partial<DashboardStats> = {}): DashboardStats =>
  ({
    total_users: 8412,
    available: 5103,
    active: 1228,
    banned: 61,
    configs_today: 326,
    referrals: 420,
    range_days: 7,
    new_today: 136,
    new_this_week: 381,
    growth_pct: 12.4,
    signups_in_range: 1180,
    signups_prev_range: 1042,
    signups_delta_pct: 13.2,
    claims_in_range: 2841,
    claims_prev_range: 2610,
    claims_delta_pct: 8.8,
    claimers_in_range: 1228,
    claimers_prev_range: 1266,
    claimers_delta_pct: -3,
    online_now: 312,
    online_squad_scoped: true,
    online_last_day: 498,
    online_last_week: 512,
    never_online: 900,
    panel_online: true,
    panel_status_counts: {},
    panel_total_users: 8412,
    total_traffic_bytes: 3.375e12,
    nodes_online: 4,
    conversion_pct: 86,
    reminder_enabled: 4102,
    avg_referrals: 0.42,
    claims_series: DAYS.map((day, i) => ({ day, count: 100 + i * 10 })),
    signups_series: DAYS.map((day, i) => ({ day, count: 40 + i })),
    languages: [{ label: "fa", count: 5240 }],
    top_locations: [{ label: "Germany", count: 1883 }],
    top_referrers: [{ telegram_id: 7314829, referral_count: 420 }],
    ...over,
  }) as DashboardStats;

const analytics = (over: Partial<DashboardAnalytics> = {}): DashboardAnalytics =>
  ({
    range_days: 7,
    dau: 498,
    wau: 1228,
    mau: 3140,
    stickiness_pct: 15.9,
    median_hours_to_claim: { value: 6.92, previous: 7.85, change_pct: -11.8 },
    activation_24h: { value: 74, previous: 71.2, change_pct: 3.9 },
    first_claimers_in_range: 1180,
    claimers_all_time: 7231,
    referral: {
      joined: 4206,
      joined_claimed: 2610,
      invitee_conversion_pct: 62,
      k_factor: 0.42,
      eligible: 6800,
      joined_share_pct: 61.9,
    },
    referral_cap: { limit: 10, at_cap: 210, with_referrals: 1840 },
    heatmap: [
      { dow: 0, hour: 9, count: 5 },
      { dow: 1, hour: 21, count: 400 },
      { dow: 2, hour: 21, count: 265 },
    ],
    signup_heatmap: [],
    claims_distribution: {},
    reminder_by_language: [],
    active_users_series: [],
    new_vs_returning: [],
    ...over,
  }) as DashboardAnalytics;

const retention: Retention = {
  weeks: 8,
  cohorts: [
    { week: "2026-06-01", size: 400, retention: [100, 60, 40] },
    { week: "2026-06-08", size: 500, retention: [100, 70] },
    { week: "2026-06-15", size: 300, retention: [100] }, // no week-two column yet
  ],
};

function renderOverview(props: Partial<Parameters<typeof Overview>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <I18nProvider>
          <Overview
            stats={stats()}
            analytics={analytics()}
            retention={retention}
            range={7}
            ranges={[7, 14, 30, 90]}
            onRange={() => {}}
            onExport={() => {}}
            exporting={false}
            {...props}
          />
        </I18nProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Overview", () => {
  it("labels each day with the weekday it actually is", () => {
    // getUTCDay() is 0 = SUNDAY. A table written starting at شنبه (Saturday) is off by one all
    // week, which had 2026-08-04 — a Tuesday — labelled دوشنبه.
    renderOverview();
    const chart = screen.getByRole("img", {
      name: "کانفیگ داده‌شده و کاربران جدید در بازهٔ انتخابی",
    });
    const labels = [...chart.querySelectorAll("text")].map((t) => t.textContent);
    // 2026-08-01 is Saturday → شنبه, and 2026-08-04 is Tuesday → سه‌شنبه.
    expect(labels).toContain("ش");
    const day4 = [...chart.querySelectorAll("text")].findIndex((t) => t.textContent === "۴");
    expect(chart.querySelectorAll("text")[day4 + 1].textContent).toBe("س");
  });

  it("weights week-two retention by cohort size, over the cohorts that HAVE a week two", () => {
    // The youngest cohort has no second column yet; counting it as 0% would drag the rate down
    // purely because the week has not happened. And the average is of PEOPLE, not of weeks: a
    // 400-person cohort must not count the same as a 500-person one.
    renderOverview();
    const radar = screen.getByRole("img", { name: "نرخ‌های کلیدی، بر حسب درصد" });
    expect(radar.textContent).toContain("بازگشت");
    // (60×400 + 70×500) / 900 = 65.6 — not the unweighted 65, and not 43.3 with the young cohort.
    expect(radar.textContent).toContain("۶۵٫۶٪");
  });

  it("prints each rate beside its own axis", () => {
    // Hovering a vertex was the only way to read a value off this chart: undiscoverable, useless
    // at a glance, and absent from a screenshot.
    renderOverview();
    const radar = screen.getByRole("img", { name: "نرخ‌های کلیدی، بر حسب درصد" });
    expect(radar.textContent).toContain("۸۶٪"); // conversion_pct
  });

  it("leads with what the service delivered, not a median that never moves", () => {
    renderOverview();
    // claims_in_range, with its own previous-window delta.
    expect(screen.getByText("۲٬۸۴۱")).toBeInTheDocument();
  });

  it("reports the peak claim hour summed across weekdays", () => {
    renderOverview();
    expect(screen.getByText("۲۱:۰۰")).toBeInTheDocument();
    expect(screen.getByText("۶۶۵")).toBeInTheDocument(); // 400 + 265
  });

  it("says so when the panel is unreachable instead of showing a silent flat line", () => {
    renderOverview({ stats: stats({ panel_online: false }) });
    expect(screen.getByText(/پنل در دسترس نیست/)).toBeInTheDocument();
  });
});
