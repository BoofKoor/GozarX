import { Clock, Download, Globe2, Languages, Loader2, MapPin, Radio, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";

import { AreaTrend } from "@/components/charts/AreaTrend";
import { HeroSparkline } from "@/components/charts/HeroSparkline";
import { RadarRates } from "@/components/charts/RadarRates";
import { SidePanel } from "@/components/layout/chrome";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import { t, useI18n, type MessageKey } from "@/i18n";
import { faPct, formatMs, formatNumber, humanBytes, langLabel, localizeDigits } from "@/lib/format";
import { webhookState, type WebhookState } from "@/lib/health";
import type { DashboardAnalytics, DashboardStats, Retention, SystemHealth } from "@/types/api";

import { GaugeCard, HealthRow, SideHead } from "./SidePanel";
import { Delta, KpiTile, TopCard } from "./tiles";

// Indexed by getUTCDay(), which is 0 = SUNDAY. A table written starting at Saturday is off by one
// all week — 2026-08-04 is a Tuesday and was labelling itself دوشنبه.
const DOW_INITIALS = [
  "d.dowInitial.0",
  "d.dowInitial.1",
  "d.dowInitial.2",
  "d.dowInitial.3",
  "d.dowInitial.4",
  "d.dowInitial.5",
  "d.dowInitial.6",
] as const;

/** "YYYY-MM-DD" → the day number and, under it, the weekday initial in the active language. */
function axisLabel(iso: string) {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return { primary: iso };
  return {
    primary: localizeDigits(String(d.getUTCDate())),
    secondary: t(DOW_INITIALS[d.getUTCDay()]),
  };
}

/**
 * Gridline steps that read as round numbers, at every order of magnitude.
 *
 * Deliberately coarse. A finer ladder (…6, 8…) frames the data more tightly, but a chart peaking
 * at 305 then gets labelled ۸۰ / ۱۶۰ / ۲۴۰ / ۳۲۰ — arithmetically snug and useless to read a
 * figure against. Round hundreds and a little more air is the better trade.
 */
const NICE_STEPS = [1, 1.5, 2, 2.5, 3, 4, 5, 10];

/**
 * Five round ticks whose TOP sits strictly above the data.
 *
 * The step is chosen first and the ceiling is four of them, so every gridline is a round figure —
 * rounding the ceiling up instead and quartering it labelled a 300-high chart ۷۵ / ۱۵۰ / ۲۲۵.
 * `AreaTrend` scales to this top, so the tallest curve always keeps headroom below the last line
 * rather than flattening against it.
 */
export function ticksFor(max: number): number[] {
  if (max <= 0) return [0, 1, 2, 3, 4];
  const decade = Math.pow(10, Math.floor(Math.log10(max / 4)));
  const raw = NICE_STEPS.map((n) => n * decade).find((s) => s * 4 > max) ?? decade * 10;
  // Whole numbers: every series here is a count of users or claims.
  let step = Math.max(1, Math.round(raw));
  if (step * 4 <= max) step += 1;
  return [0, step, step * 2, step * 3, step * 4];
}

const WEBHOOK_TONE: Record<WebhookState, "ok" | "warn" | "bad" | "idle"> = {
  checking: "idle",
  off: "bad",
  unreachable: "warn",
  unregistered: "bad",
  error: "warn",
  backlog: "warn",
  ok: "ok",
};

const WEBHOOK_LABEL: Record<WebhookState, MessageKey> = {
  checking: "dash.health.checking",
  off: "dash.health.webhookUnset",
  unreachable: "dash.health.webhookUnreachable",
  unregistered: "dash.health.webhookUnregistered",
  error: "dash.health.webhookError",
  backlog: "dash.health.webhookBacklog",
  ok: "dash.health.webhookOk",
};

/**
 * The dashboard's overview: the KPI band, the activity trend, the "top" cards, and the side rail of
 * live figures.
 *
 * Everything here is derived from data the system already records. Where the design showed a figure
 * the product cannot produce — an all-time online peak to gauge against, an open rate Telegram
 * never reports — the tile carries a real, nameable denominator instead of an invented one.
 */
export function Overview({
  stats,
  analytics,
  retention,
  health,
  range,
  ranges,
  onRange,
  pending = false,
  onExport,
  exporting,
}: {
  stats: DashboardStats;
  analytics?: DashboardAnalytics;
  retention?: Retention;
  health?: SystemHealth;
  /** The range the operator ASKED for — the control shows it at once, whatever is on screen. */
  range: number;
  ranges: readonly number[];
  onRange: (n: number) => void;
  /** The figures on screen are still the previous range's, and the asked-for one is loading. */
  pending?: boolean;
  onExport: () => void;
  exporting: boolean;
}) {
  const { t } = useI18n();
  const hook = webhookState(health);
  const claims = stats.claims_series;
  const signups = stats.signups_series;
  // Each line on its OWN scale: signups run at ~1% of claims, and on one shared axis their line
  // was a flat stroke along the floor.
  const maxClaims = Math.max(1, ...claims.map((d) => d.count));
  const maxSignups = Math.max(1, ...signups.map((d) => d.count));
  // The window the figures on screen describe (the asked-for one may still be loading).
  const shownDays = stats.range_days;
  const inRange = t("dash.scope.range", { n: formatNumber(shownDays) });
  const allTime = t("dash.scope.allTime");

  // The hero sparkline shows how the total GREW each day, not the running total itself: a
  // cumulative curve over one week is a near-straight ramp, which is a shape with no information
  // in it. The marker sits on the best day, which is a day the ramp could never point at.
  //
  // The last SEVEN COMPLETE days: today is still filling, and as the curve's final point it drew
  // every morning as a collapse — the one shape a growth sparkline must not fake.
  const tail = signups.slice(0, -1).slice(-7);
  const peak = tail.length
    ? tail.reduce((best, d, i) => (d.count > tail[best].count ? i : best), 0)
    : 0;

  const avgPerClaimer =
    stats.claimers_in_range > 0 ? stats.claims_in_range / stats.claimers_in_range : 0;
  const avgPrev =
    stats.claimers_prev_range > 0 ? stats.claims_prev_range / stats.claimers_prev_range : 0;
  const avgDelta = avgPrev > 0 ? ((avgPerClaimer - avgPrev) / avgPrev) * 100 : null;

  // "Returned in week two" is the second column of every weekly cohort — the retention matrix
  // already computes it, so the radar reuses it rather than asking for a new figure.
  //
  // WEIGHTED by cohort size. A plain mean let a 509-user launch week count as much as the
  // 15,757-user week beside it, which is not an average of the population — it is an average of
  // the weeks. Rows still shorter than two columns are cohorts whose second week has not arrived;
  // the server now sizes rows by ELAPSED weeks, so a cohort nobody returned to carries a real 0
  // instead of being dropped for looking the same as one that is two days old.
  const weekTwo = (() => {
    if (!retention) return null; // not loaded (or failed): no reading, not a 0%
    const rows = retention.cohorts.filter((c) => c.retention.length > 1 && c.size > 0);
    const people = rows.reduce((a, c) => a + c.size, 0);
    // No cohort old enough to HAVE a week two: nothing was measured, so «—», not «۰٪» — the same
    // answer the activation axis beside it gives for an empty cohort.
    if (!people) return null;
    return rows.reduce((a, c) => a + c.retention[1] * c.size, 0) / people;
  })();
  // Of everyone who has ever claimed, the share who claimed more than once. Read off the claims
  // distribution the analytics endpoint already returns, so it costs no query.
  //
  // This replaced the referral share on the radar. 17% is a perfectly good referral rate for a
  // free service, but on an axis shared with an 86% it draws as a stub, and the operator reported
  // the chart as broken twice because of it. Repeat rate asks something no other axis asks —
  // retention is time-bound ("did they come back next week"), this is habit ("did they come back
  // at all") — and it lands at 52% on live data, inside the band the other three occupy.
  //
  // Not chosen: the reminder opt-in rate, which measures 99.7% because the setting ships on. An
  // axis pinned to its own ceiling forever carries no information at all.
  const repeatRate = (() => {
    if (!analytics) return null;
    const buckets = analytics.claims_distribution;
    const claimers = Object.values(buckets).reduce((a, n) => a + n, 0);
    if (!claimers) return null; // nobody has claimed yet: no reading, not a 0% habit
    return ((claimers - (buckets["1"] ?? 0)) / claimers) * 100;
  })();

  const peakHour = (() => {
    const byHour = new Map<number, number>();
    for (const cell of analytics?.heatmap ?? [])
      byHour.set(cell.hour, (byHour.get(cell.hour) ?? 0) + cell.count);
    let best = -1;
    let bestN = 0;
    for (const [h, n] of byHour) if (n > bestN) [best, bestN] = [h, n];
    return { hour: best, count: bestN };
  })();

  const topLocation = stats.top_locations[0];
  const topReferrer = stats.top_referrers[0];
  const topLanguage = stats.languages[0];

  return (
    // No side column here any more: the live figures are their own PANEL beside the console, which
    // is where the design puts them, so the trend and the tiles get the console's full width.
    <div className="flex flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-4">
        {/* `items-start`, not the grid default: the design's `.kpis` is `align-items: start` and
            keeps a plain tile at its own `min-height: 8.7rem` while the hero runs taller for its
            sparkline. Stretched to the hero's height instead, each plain tile measured 222px
            against the design's 139 — 98px of nothing between its label and the delta pinned to
            the floor by `mt-auto`, three times across the band. */}
        <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-[1.22fr_repeat(3,1fr)]">
          {/* Deliberately NOT spanning the row when there are two columns. The sparkline's height
              follows its width, so a full-width hero at 768px draws a 650px-tall chart inside a KPI
              tile; at half width it lands on the ~245px the design draws, and the tile beside it
              stretches to match, which is what the design does too. */}
          <KpiTile hero value={formatNumber(stats.total_users)} label={t("dash.kpi.total")}>
            {tail.length >= 2 && (
              // Pushed to the bottom of the tile and bled past its padding on three sides, so the
              // curve runs edge to edge and the marker column reaches the tile's own floor.
              <div className="-mx-4 -mb-2 mt-auto pt-3">
                <HeroSparkline
                  values={tail.map((d) => d.count)}
                  labels={tail.map((d) => axisLabel(d.day).secondary ?? "")}
                  highlight={peak}
                  delta={
                    stats.growth_pct != null
                      ? `${stats.growth_pct >= 0 ? "+" : ""}${faPct(stats.growth_pct)}`
                      : undefined
                  }
                  ariaLabel={t("dash.spark.aria", {
                    days: formatNumber(tail.length),
                    peak: formatNumber(tail[peak].count),
                  })}
                />
              </div>
            )}
          </KpiTile>

          <KpiTile
            value={formatNumber(stats.claimers_in_range)}
            label={t("dash.kpi.active", { days: formatNumber(shownDays) })}
            delta={<Delta pct={stats.claimers_delta_pct} newLabel={t("dash.delta.first")} />}
          />
          {/* Configs delivered, not the activation median. The median is a real figure and a good
              one — 21 seconds — but it is a property of the bot's flow, so it does not move from
              one day to the next and a headline tile that never changes is a tile that stops being
              read. It keeps its place on the growth tab, where a jump from 21s to four hours is
              the kind of thing anyone would be looking for. This slot now carries what the service
              actually did in the window. */}
          <KpiTile
            value={formatNumber(stats.claims_in_range)}
            label={t("dash.kpi.claims", { days: formatNumber(shownDays) })}
            delta={<Delta pct={stats.claims_delta_pct} newLabel={t("dash.delta.first")} />}
          />
          <KpiTile
            value={formatNumber(Math.round(avgPerClaimer * 10) / 10)}
            label={t("dash.kpi.perUser")}
            delta={<Delta pct={avgDelta} newLabel={t("dash.delta.first")} />}
          />
        </div>

        {/* No card: the trend sits directly on the well, as the design does. Boxing it made the
            panel's largest element the only thing on the page with a frame around it. */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="min-w-0">
              <h3 className="text-base font-bold text-content">{t("dash.chart.title")}</h3>
              <p className="mt-0.5 text-xs text-content-subtle">{t("dash.chart.sub")}</p>
            </div>
            <span className="flex-1" />
            {/* The control moves the moment it is pressed; what follows is the data catching up.
                Held on the old range until the new figures landed, a slow window read as a
                control that had not registered the click at all. */}
            {pending && <RangeLoading />}
            <Segmented
              value={String(range)}
              onChange={(v) => onRange(Number(v))}
              options={ranges.map((n) => ({
                value: String(n),
                label: t("dash.range.days", { n: formatNumber(n) }),
              }))}
              size="sm"
              ariaLabel={t("dash.range.aria")}
            />
            <Button size="sm" onClick={onExport} loading={exporting}>
              <Download className="h-4 w-4" />
              {t("dash.export")}
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-content-muted">
            <span className="inline-flex items-center gap-1.5">
              <i className="h-2 w-2 rounded-full bg-chart-1" aria-hidden />
              {t("dash.chart.claims")}
              <span className="text-content-subtle">{t("dash.chart.leftAxis")}</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <i className="h-2 w-2 rounded-full bg-chart-2" aria-hidden />
              {t("dash.chart.signups")}
              <span className="text-content-subtle">{t("dash.chart.rightAxis")}</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <svg width="14" height="2" aria-hidden className="text-content-subtle">
                <line
                  x1="0"
                  y1="1"
                  x2="14"
                  y2="1"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeDasharray="3 2"
                />
              </svg>
              {t("dash.chart.partial")}
            </span>
            {/* The panel being unreachable is a real state the stats endpoint reports, and it
                explains a flat line better than any tooltip can. */}
            {!stats.panel_online && (
              <span className="inline-flex items-center gap-1.5 text-danger-700">
                <i className="h-2 w-2 rounded-full bg-danger-500" aria-hidden />
                {t("dash.chart.panelDown")}
              </span>
            )}
          </div>

          <div
            aria-busy={pending || undefined}
            className={pending ? "opacity-60 transition-opacity" : "transition-opacity"}
          >
            <AreaTrend
              series={[
                { values: claims.map((d) => d.count), label: t("dash.chart.claims") },
                {
                  values: signups.map((d) => d.count),
                  label: t("dash.chart.signups"),
                  axis: "secondary",
                },
              ]}
              labels={claims.map((d) => axisLabel(d.day))}
              ticks={ticksFor(maxClaims)}
              secondaryTicks={ticksFor(maxSignups)}
              // The series always ends on TODAY, which is still filling.
              partialLast
              partialLabel={t("dash.chart.soFar")}
              formatValue={formatNumber}
              ariaLabel={t("dash.chart.sub")}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TopCard
            icon={MapPin}
            tone={1}
            label={t("dash.top.location")}
            scope={inRange}
            headline={topLocation?.label ?? "—"}
            value={formatNumber(topLocation?.count ?? 0)}
            unit={t("dash.unit.claims")}
          />
          {/* Lifetime, and SAID so: a referral count is a running total, and the language is
              every user's current setting. Beside two windowed cards, unlabelled, they read as
              figures the range control had moved. */}
          <TopCard
            icon={UserPlus}
            tone={2}
            label={t("dash.top.referrer")}
            scope={allTime}
            headline={topReferrer ? String(topReferrer.telegram_id) : "—"}
            value={formatNumber(topReferrer?.referral_count ?? 0)}
            unit={t("dash.unit.invites")}
            mono
          />
          <TopCard
            icon={Languages}
            tone={3}
            label={t("dash.top.language")}
            scope={allTime}
            headline={topLanguage ? langLabel(topLanguage.label) : "—"}
            value={formatNumber(topLanguage?.count ?? 0)}
            unit={t("dash.unit.users")}
          />
          <TopCard
            icon={Clock}
            tone={4}
            label={t("dash.top.hour")}
            scope={inRange}
            headline={
              peakHour.hour < 0
                ? "—"
                : localizeDigits(`${String(peakHour.hour).padStart(2, "0")}:00`)
            }
            value={formatNumber(peakHour.count)}
            unit={t("dash.unit.claims")}
          />
        </div>
      </div>

      <SidePanel>
        <SideHead>{t("dash.side.rates")}</SideHead>
        {/* Index 0 is the TOP spoke, 1 right, 2 bottom, 3 left. The order is the funnel — reach,
            speed, return, habit — which also happens to be what the shape needs: it puts the two
            largest rates ADJACENT instead of facing each other. Facing, they pull the blob into a
            symmetric lens, which is a silhouette rather than a chart, and the previous order did
            exactly that while carrying a comment saying it did the opposite.

            A funnel order rather than a sorted one on purpose: sorting by value would reshuffle
            the axes as the data moved, and a chart whose axes change places is unreadable across
            two visits. */}
        <RadarRates
          axes={[
            {
              // WINDOWED — of this range's signups, who claimed. The lifetime ratio it replaced
              // sat beside three windowed rates and did not move when the range did.
              label: t("dash.rate.conversion"),
              value: stats.conversion.value,
              title: t("dash.rate.conversionFull"),
            },
            {
              label: t("dash.rate.activation"),
              value: analytics ? analytics.activation_24h.value : null,
              title: t("dash.rate.activationFull"),
            },
            { label: t("dash.rate.return"), value: weekTwo, title: t("dash.rate.returnFull") },
            { label: t("dash.rate.repeat"), value: repeatRate, title: t("dash.rate.repeatFull") },
          ]}
          className="w-full"
        />

        <SideHead>{t("dash.side.live")}</SideHead>
        {/* Numerator and denominator from ONE population: the trial squad's online count over
            the trial squad's week, or the panel's over the panel's. It used to divide the squad
            count by the whole panel's week, which also held the operator's own users. */}
        <GaugeCard
          icon={Radio}
          label={t("dash.live.online")}
          value={stats.online_now}
          outOf={
            stats.online_now == null || stats.online_week == null
              ? null
              : Math.max(stats.online_now, stats.online_week)
          }
          outOfLabel={t("dash.live.onlineOf")}
        />
        <GaugeCard
          icon={UserPlus}
          label={t("dash.live.newToday")}
          value={stats.new_today}
          outOf={Math.max(stats.new_today, stats.new_this_week)}
          outOfLabel={t("dash.live.newTodayOf")}
        />
        <div className="flex items-center gap-3 rounded-[13px] bg-surface-raised px-[0.9rem] py-[0.8rem]">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[0.8rem] leading-[1.4] text-content-muted">
              {t("dash.live.traffic")}
            </div>
            {/* Lifetime, and labelled as such — a delta on an all-time total is meaningless. */}
            <div className="text-[11px] text-content-subtle">{t("dash.live.trafficSub")}</div>
          </div>
          <span className="shrink-0 text-[1.4rem] font-bold tracking-[-0.02em] tabular-nums text-content">
            {/* Unknown is "—": the panel being down is not the service having carried 0 B. */}
            {stats.total_traffic_bytes == null ? "—" : humanBytes(stats.total_traffic_bytes)}
          </span>
        </div>

        <SideHead>{t("dash.side.health")}</SideHead>
        <div className="rounded-[13px] bg-surface-raised px-[0.9rem] py-1">
          <HealthRow
            label={t("dash.health.panel")}
            tone={!health ? "idle" : health.panel.ok ? "ok" : "bad"}
            value={
              !health
                ? t("dash.health.checking")
                : health.panel.latency_ms != null
                  ? formatMs(health.panel.latency_ms)
                  : "—"
            }
          />
          <HealthRow
            label={t("dash.health.webhook")}
            tone={WEBHOOK_TONE[hook]}
            value={t(WEBHOOK_LABEL[hook], { n: formatNumber(health?.webhook.pending ?? 0) })}
          />
          {/* LIVE trials, with the stale remainder named: the status column is healed only by
              the webhook or the reconcile sweep, which skips users while the panel is down, so the
              raw count kept every expired trial of an outage in "active". */}
          <HealthRow
            label={t("dash.health.activeConfigs")}
            hint={
              stats.active_stale > 0
                ? t("dash.health.activeStale", { n: formatNumber(stats.active_stale) })
                : undefined
            }
            tone={stats.active_stale > 0 ? "warn" : stats.active_live > 0 ? "ok" : "warn"}
            value={`${formatNumber(stats.active_live)} ${t("dash.unit.users")}`}
          />
          <HealthRow
            last
            label={t("dash.health.conversionRange", { n: formatNumber(shownDays) })}
            tone={
              stats.conversion.value == null ? "idle" : stats.conversion.value >= 50 ? "ok" : "warn"
            }
            value={stats.conversion.value == null ? "—" : faPct(stats.conversion.value)}
          />
        </div>

        {/* `py-1.5` takes the link from a 16px-tall target to 24 (WCAG 2.5.8's floor), and
            `text-brand-700` is the ramp's ink shade — `text-brand` is the FILL shade and measured
            3.14:1 here. */}
        {/* A router link: an <a href> reloaded the whole console — every cached query gone, the
            setup gate asked again — to move one page over. */}
        <Link
          to="/system"
          className="mt-1 inline-flex items-center gap-1.5 px-1 py-1.5 text-xs font-medium text-brand-700 hover:underline"
        >
          <Globe2 className="h-3.5 w-3.5" />
          {t("dash.health.more")}
        </Link>
      </SidePanel>
    </div>
  );
}

/** A small, announced "loading the new range" mark beside the range control. */
function RangeLoading() {
  const { t } = useI18n();
  return (
    <span role="status" className="inline-flex items-center gap-1.5 text-xs text-content-subtle">
      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
      {t("dash.range.loading")}
    </span>
  );
}
