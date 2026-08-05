import { Clock, Download, Globe2, Languages, MapPin, Radio, UserPlus } from "lucide-react";

import { AreaTrend } from "@/components/charts/AreaTrend";
import { HeroSparkline } from "@/components/charts/HeroSparkline";
import { RadarRates } from "@/components/charts/RadarRates";
import { SidePanel } from "@/components/layout/chrome";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import { t, useI18n } from "@/i18n";
import { faPct, formatNumber, humanBytes, langLabel, localizeDigits } from "@/lib/format";
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
  onExport,
  exporting,
}: {
  stats: DashboardStats;
  analytics?: DashboardAnalytics;
  retention?: Retention;
  health?: SystemHealth;
  range: number;
  ranges: readonly number[];
  onRange: (n: number) => void;
  onExport: () => void;
  exporting: boolean;
}) {
  const { t } = useI18n();
  const claims = stats.claims_series;
  const signups = stats.signups_series;
  const maxY = Math.max(1, ...claims.map((d) => d.count), ...signups.map((d) => d.count));

  // The hero sparkline shows how the total GREW each day, not the running total itself: a
  // cumulative curve over one week is a near-straight ramp, which is a shape with no information
  // in it. The marker sits on the best day, which is a day the ramp could never point at.
  const tail = signups.slice(-7);
  const peak = tail.length
    ? tail.reduce((best, d, i) => (d.count > tail[best].count ? i : best), 0)
    : 0;

  const avgPerClaimer =
    stats.claimers_in_range > 0 ? stats.claims_in_range / stats.claimers_in_range : 0;
  const avgPrev =
    stats.claimers_prev_range > 0 ? stats.claims_prev_range / stats.claimers_prev_range : 0;
  const avgDelta = avgPrev > 0 ? ((avgPerClaimer - avgPrev) / avgPrev) * 100 : null;

  // "Returned in week two" is the second column of every weekly cohort, averaged — the retention
  // matrix already computes it, so the radar reuses it rather than asking for a new figure.
  const weekTwo = (() => {
    const rows = (retention?.cohorts ?? []).filter((c) => c.retention.length > 1 && c.size > 0);
    if (!rows.length) return 0;
    return rows.reduce((a, c) => a + c.retention[1], 0) / rows.length;
  })();
  const referralShare =
    stats.total_users > 0 && analytics ? (analytics.referral.joined / stats.total_users) * 100 : 0;

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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1.22fr_repeat(3,1fr)]">
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
            label={t("dash.kpi.active", { days: formatNumber(range) })}
            delta={<Delta pct={stats.claimers_delta_pct} newLabel={t("dash.delta.first")} />}
          />
          <KpiTile
            value={
              analytics?.median_hours_to_claim.value == null
                ? "—"
                : formatNumber(analytics.median_hours_to_claim.value)
            }
            label={t("dash.kpi.median")}
            delta={
              <Delta
                pct={analytics?.median_hours_to_claim.change_pct}
                goodWhenDown
                newLabel={t("dash.delta.noBase")}
              />
            }
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
            </span>
            <span className="inline-flex items-center gap-1.5">
              <i className="h-2 w-2 rounded-full bg-chart-2" aria-hidden />
              {t("dash.chart.signups")}
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

          <AreaTrend
            series={[
              { values: claims.map((d) => d.count), label: t("dash.chart.claims") },
              { values: signups.map((d) => d.count), label: t("dash.chart.signups") },
            ]}
            labels={claims.map((d) => axisLabel(d.day))}
            ticks={ticksFor(maxY)}
            formatValue={formatNumber}
            ariaLabel={t("dash.chart.sub")}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TopCard
            icon={MapPin}
            tone={1}
            label={t("dash.top.location")}
            headline={topLocation?.label ?? "—"}
            value={formatNumber(topLocation?.count ?? 0)}
            unit={t("dash.unit.claims")}
          />
          <TopCard
            icon={UserPlus}
            tone={2}
            label={t("dash.top.referrer")}
            headline={topReferrer ? String(topReferrer.telegram_id) : "—"}
            value={formatNumber(topReferrer?.referral_count ?? 0)}
            unit={t("dash.unit.invites")}
            mono
          />
          <TopCard
            icon={Languages}
            tone={3}
            label={t("dash.top.language")}
            headline={topLanguage ? langLabel(topLanguage.label) : "—"}
            value={formatNumber(topLanguage?.count ?? 0)}
            unit={t("dash.unit.users")}
          />
          <TopCard
            icon={Clock}
            tone={4}
            label={t("dash.top.hour")}
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
        {/* Ordered so the two extremes land ADJACENT: four axes with the big values facing each
            other collapse into a lens, which is a shape rather than a chart. */}
        <RadarRates
          axes={[
            {
              label: t("dash.rate.conversion"),
              value: stats.conversion_pct,
              title: t("dash.rate.conversionFull"),
            },
            { label: t("dash.rate.return"), value: weekTwo, title: t("dash.rate.returnFull") },
            {
              label: t("dash.rate.activation"),
              value: analytics?.activation_24h.value ?? 0,
              title: t("dash.rate.activationFull"),
            },
            {
              label: t("dash.rate.referral"),
              value: referralShare,
              title: t("dash.rate.referralFull"),
            },
          ]}
          className="w-full"
        />

        <SideHead>{t("dash.side.live")}</SideHead>
        <GaugeCard
          icon={Radio}
          label={t("dash.live.online")}
          value={stats.online_now}
          outOf={Math.max(stats.online_now, stats.online_last_week)}
          outOfLabel={t("dash.live.onlineOf")}
        />
        <GaugeCard
          icon={UserPlus}
          label={t("dash.live.newToday")}
          value={stats.new_today}
          outOf={Math.max(stats.new_today, stats.new_this_week)}
          outOfLabel={t("dash.live.newTodayOf")}
        />
        <div className="flex items-center gap-3 rounded-xl bg-surface-raised p-3">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm text-content-muted">{t("dash.live.traffic")}</div>
            {/* Lifetime, and labelled as such — a delta on an all-time total is meaningless. */}
            <div className="text-[11px] text-content-subtle">{t("dash.live.trafficSub")}</div>
          </div>
          <span className="shrink-0 text-lg font-bold tabular-nums text-content">
            {humanBytes(stats.total_traffic_bytes)}
          </span>
        </div>

        <SideHead>{t("dash.side.health")}</SideHead>
        <div className="rounded-xl bg-surface-raised px-3 py-1">
          <HealthRow
            label={t("dash.health.panel")}
            tone={health?.panel.ok ? "ok" : "bad"}
            value={
              health?.panel.latency_ms != null
                ? localizeDigits(`${Math.round(health.panel.latency_ms)} ms`)
                : "—"
            }
          />
          <HealthRow
            label={t("dash.health.webhook")}
            tone={!health?.webhook.configured ? "bad" : health.webhook.recent_error ? "warn" : "ok"}
            value={
              !health?.webhook.configured
                ? t("dash.health.webhookUnset")
                : health.webhook.recent_error
                  ? t("dash.health.webhookError")
                  : t("dash.health.webhookOk")
            }
          />
          <HealthRow
            label={t("dash.health.activeConfigs")}
            tone={stats.active > 0 ? "ok" : "warn"}
            value={`${formatNumber(stats.active)} ${t("dash.unit.users")}`}
          />
          <HealthRow
            last
            label={t("dash.health.conversion")}
            tone={stats.conversion_pct >= 50 ? "ok" : "warn"}
            value={faPct(stats.conversion_pct)}
          />
        </div>

        <a
          href="/admin/system"
          className="mt-1 inline-flex items-center gap-1.5 px-1 text-xs font-medium text-brand hover:underline"
        >
          <Globe2 className="h-3.5 w-3.5" />
          {t("dash.health.more")}
        </a>
      </SidePanel>
    </div>
  );
}
