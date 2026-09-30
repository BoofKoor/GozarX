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
    active_live: 1228,
    active_stale: 0,
    online_now: 312,
    online_squad_scoped: true,
    online_week: 512,
    online_last_day: 498,
    online_last_week: 512,
    never_online: 900,
    panel_online: true,
    panel_status_counts: {},
    panel_total_users: 8412,
    total_traffic_bytes: 3.375e12,
    nodes_online: 4,
    conversion: { value: 86, previous: 80, change_pct: 7.5 },
    conversion_pct_all_time: 71,
    reminder_enabled: 4102,
    avg_referrals: 0.42,
    claims_series: DAYS.map((day, i) => ({ day, count: 100 + i * 10 })),
    signups_series: DAYS.map((day, i) => ({ day, count: 40 + i })),
    languages: [{ label: "fa", count: 5240 }],
    top_locations: [{ label: "Germany", count: 1883 }],
    locations_total: 1,
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
    // Backs the repeat-rate axis: 300 claimers, 120 of them once-only → 60%.
    claims_distribution: { "1": 120, "2-3": 100, "4-6": 50, "7+": 30 },
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
    expect(radar.textContent).toContain("۸۶٪"); // the WINDOWED conversion, not the lifetime 71
    expect(radar.textContent).not.toContain("۷۱٪");
  });

  it("puts the two largest rates ADJACENT, not facing each other", () => {
    // Index 0 is the top spoke, 1 right, 2 bottom, 3 left. Facing, the two big values pull the
    // blob into a symmetric lens — which is what the previous order did while its comment claimed
    // the opposite.
    renderOverview();
    const radar = screen.getByRole("img", { name: "نرخ‌های کلیدی، بر حسب درصد" });
    const labels = [...radar.querySelectorAll("text")].map((n) => n.textContent);
    const order = labels.filter((l) => ["تبدیل", "فعال‌سازی", "بازگشت", "تکرار"].includes(l!));
    // conversion (86) and activation (74) are neighbours; the two smaller rates take the far side.
    expect(order.slice(0, 2)).toEqual(["تبدیل", "فعال‌سازی"]);
  });

  it("carries repeat rate rather than the referral stub", () => {
    // 17% is a fine referral rate; on an axis shared with an 86% it draws as a stub and the chart
    // got reported as broken. Repeat rate asks something no other axis asks and sits in the band.
    renderOverview();
    const radar = screen.getByRole("img", { name: "نرخ‌های کلیدی، بر حسب درصد" });
    expect(radar.textContent).toContain("۶۰٪"); // (300 - 120) / 300
    expect(radar.textContent).not.toContain("دعوت");
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

  it("gauges online users against the SAME population's week", () => {
    // Squad-scoped online over the squad's own week — never over the panel-wide week, which also
    // counts the operator's own users (5,000 here, which would draw a near-empty ring).
    renderOverview({ stats: stats({ online_now: 90, online_week: 300, online_last_week: 5000 }) });
    expect(screen.getByText(/فعال هفته\s*۳۰۰/)).toBeInTheDocument();
    expect(screen.queryByText(/۵٬۰۰۰/)).not.toBeInTheDocument();
  });

  it("says unknown rather than zero when the panel did not answer", () => {
    renderOverview({
      stats: stats({
        panel_online: false,
        online_now: null,
        online_week: null,
        total_traffic_bytes: null,
      }),
    });
    // The traffic tile and the online gauge both read "—", not «۰ B» and «۰».
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/B$/)).not.toBeInTheDocument();
  });

  it("labels which top cards are lifetime and which follow the range", () => {
    renderOverview();
    expect(screen.getAllByText(/کل دوره/)).toHaveLength(2); // top referrer + top language
    expect(screen.getAllByText(/· ۷ روز/)).toHaveLength(2); // top location + peak hour
  });

  it("counts only LIVE trials as active and names the stale remainder", () => {
    renderOverview({ stats: stats({ active: 1250, active_live: 1200, active_stale: 50 }) });
    expect(screen.getByText("۱٬۲۰۰ کاربر")).toBeInTheDocument();
    expect(screen.getByText("۵۰ منقضی‌شده هنوز همگام نشده")).toBeInTheDocument();
  });

  it("moves the range control at once and says the new range is loading", () => {
    // The figures on screen are still the 7-day ones (`stats.range_days`) while 30 loads.
    renderOverview({ range: 30, pending: true });
    expect(screen.getByRole("radio", { name: "۳۰ روز" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("status")).toHaveTextContent("در حال بارگذاری بازهٔ جدید…");
    // …and the KPI labels keep describing the window actually shown.
    expect(screen.getByText("کانفیگ تحویل‌شده در ۷ روز")).toBeInTheDocument();
  });

  it("draws the still-filling last day dashed", () => {
    renderOverview();
    const chart = screen.getByRole("img", {
      name: "کانفیگ داده‌شده و کاربران جدید در بازهٔ انتخابی",
    });
    expect(chart.querySelectorAll("path[stroke-dasharray]").length).toBe(2); // one per series
  });
});
