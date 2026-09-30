import {
  Activity,
  AlertTriangle,
  Download,
  Gauge,
  Gift,
  Globe2,
  HeartPulse,
  LineChart,
  Loader2,
  Repeat,
  UserPlus,
} from "lucide-react";
import { Suspense, lazy, useState } from "react";
import { toast } from "sonner";

import { ActivationPanel } from "@/components/dashboard/ActivationPanel";
import { ActiveUsersPanel } from "@/components/dashboard/ActiveUsersPanel";
import { ActivityHeatmap } from "@/components/dashboard/ActivityHeatmap";
import { ClaimsDistribution } from "@/components/dashboard/ClaimsDistribution";
import { ConversionPanel } from "@/components/dashboard/ConversionPanel";
import { ReferralFunnelPanel } from "@/components/dashboard/ReferralFunnelPanel";
import { ReminderByLanguage } from "@/components/dashboard/ReminderByLanguage";
import { RetentionCohorts } from "@/components/dashboard/RetentionCohorts";
import { Overview } from "@/components/dashboard/overview/Overview";
import { TopLocations } from "@/components/dashboard/TopLocations";
import { TopReferrers } from "@/components/dashboard/TopReferrers";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, tabId } from "@/components/ui/Tabs";
import { useSystemHealth } from "@/hooks/useSystem";
import {
  RANGES,
  downloadDashboardCsv,
  useDashboard,
  useDashboardAnalytics,
  useDashboardUsage,
  useRetention,
} from "@/hooks/useDashboard";
import { useI18n, type MessageKey } from "@/i18n";
import { faPct, faTime, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

// The five panels that draw with recharts load with their tab, not with the page. Imported
// statically they made the dashboard's chunk depend on the 434 KB chart library, which the default
// tab — the hand-drawn overview — never uses.
const CumulativeUsersChart = lazy(() =>
  import("@/components/dashboard/CumulativeUsersChart").then((m) => ({
    default: m.CumulativeUsersChart,
  })),
);
const LanguageDonut = lazy(() =>
  import("@/components/dashboard/LanguageDonut").then((m) => ({ default: m.LanguageDonut })),
);
const NewVsReturningChart = lazy(() =>
  import("@/components/dashboard/NewVsReturningChart").then((m) => ({
    default: m.NewVsReturningChart,
  })),
);
const UsagePanel = lazy(() =>
  import("@/components/dashboard/UsagePanel").then((m) => ({ default: m.UsagePanel })),
);
const TrialHealthPanel = lazy(() =>
  import("@/components/dashboard/TrialHealthPanel").then((m) => ({
    default: m.TrialHealthPanel,
  })),
);

type TabKey = "overview" | "growth" | "retention" | "referrals" | "usage" | "geo" | "health";

const TAB_ID_BASE = "dash-tab";
const TAB_PANEL_ID = "dash-panel";

const TAB_KEYS: { value: TabKey; labelKey: MessageKey; icon: typeof LineChart }[] = [
  { value: "overview", labelKey: "dash.tab.overview", icon: LineChart },
  { value: "growth", labelKey: "dash.tab.growth", icon: UserPlus },
  { value: "retention", labelKey: "dash.tab.retention", icon: Repeat },
  { value: "referrals", labelKey: "dash.tab.referrals", icon: Gift },
  // Between referrals and geography: the tab is about LOAD on the service, which sits
  // naturally after the audience tabs and before the where-and-when ones.
  { value: "usage", labelKey: "dash.tab.usage", icon: Gauge },
  { value: "geo", labelKey: "dash.tab.geo", icon: Globe2 },
  { value: "health", labelKey: "dash.tab.health", icon: HeartPulse },
];

// Built per render rather than at module scope: the label is localized, so a constant would
// freeze whichever language happened to load first.
const RANGE_VALUES = RANGES as readonly number[];

/** Render a panel once its (separate) query has loaded, else a stable skeleton so the grid doesn't
 *  jump when the deeper stats arrive a moment after the headline.
 *
 *  Generic over the payload: the analytics query is no longer the only one that lands late — the
 *  usage series is its own request, and pinning this to one response type would mean a second copy
 *  of the same three lines. */
function Analytic<T>({
  data,
  render,
  height = "h-52",
  error = false,
  onRetry,
}: {
  data: T | undefined;
  render: (d: T) => JSX.Element;
  height?: string;
  /** The query FAILED — a skeleton would sit there forever, saying "still loading". */
  error?: boolean;
  onRetry?: () => void;
}) {
  if (!data) {
    if (error) return <ErrorState onRetry={onRetry} />;
    return (
      <Card>
        <Skeleton className={`${height} w-full`} />
      </Card>
    );
  }
  return render(data);
}

export function Dashboard() {
  const { t } = useI18n();
  const [days, setDays] = useState<number>(14);
  const TABS = TAB_KEYS.map((x) => ({ ...x, label: t(x.labelKey) }));
  const RANGE_OPTIONS = RANGE_VALUES.map((r) => ({
    value: r,
    label: t("dash.range.days", { n: formatNumber(r) }),
  }));
  const { data: health } = useSystemHealth();
  const [exporting, setExporting] = useState(false);
  const { data, isLoading, isError, refetch, dataUpdatedAt } = useDashboard(days);
  // Every windowed panel reads from these two queries, so the range control drives the WHOLE page —
  // it used to move only the activity chart while the panels beside it stayed on their own window.
  const analyticsQuery = useDashboardAnalytics(days);
  const analytics = analyticsQuery.data;
  const [tab, setTab] = useState<TabKey>("overview");
  const usageQuery = useDashboardUsage(days, tab === "usage");
  const usage = usageQuery.data;
  // Cohorts are inherently weekly, so they keep their own axis rather than the day range.
  const retentionQuery = useRetention(8);
  const retention = retentionQuery.data;
  // Every analytics-backed panel says so when that query failed, with a way to ask again.
  const analyticsState = {
    error: analyticsQuery.isError,
    onRetry: () => void analyticsQuery.refetch(),
  };

  async function exportCsv() {
    setExporting(true);
    try {
      await downloadDashboardCsv(days);
    } catch {
      toast.error(t("d.exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  // `keepPreviousData` holds the old range's figures on screen while the new one loads, which is
  // right — but without saying so the page looked as if the click had not registered, for as long
  // as the slower window took.
  const rangePending =
    (data != null && data.range_days !== days) ||
    (analytics != null && analytics.range_days !== days);
  const rangeControl = (
    <span className="inline-flex items-center gap-2">
      {rangePending && (
        <span role="status" aria-label={t("dash.range.loading")}>
          <Loader2 className="h-3.5 w-3.5 animate-spin text-content-subtle" aria-hidden />
        </span>
      )}
      <Segmented
        value={days}
        onChange={setDays}
        options={RANGE_OPTIONS}
        size="sm"
        ariaLabel={t("dash.range.aria")}
      />
    </span>
  );

  if (isLoading) {
    return <DashboardSkeleton />;
  }
  // The full error page only when there is NOTHING to show — and it keeps the range control: a
  // window that fails (90 days, say) used to take the control away with it, so "retry" could only
  // ever ask for the same failing window again.
  if (!data) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("dash.title")} actions={rangeControl} />
        <ErrorState onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("dash.title")}
        sub={t("dash.sub", { days: formatNumber(data.range_days) })}
        actions={
          // The overview carries its own range control and export button, beside the chart they
          // drive. Showing a second pair up here would be two controls for one concern.
          tab === "overview" ? undefined : (
            <>
              {rangeControl}
              <Button variant="outline" size="sm" onClick={exportCsv} loading={exporting}>
                <Download className="h-4 w-4" />
                <span className="hidden sm:inline">{t("dash.export")}</span>
              </Button>
            </>
          )
        }
      >
        <Tabs
          value={tab}
          onChange={setTab}
          items={TABS}
          idBase={TAB_ID_BASE}
          panelId={TAB_PANEL_ID}
        />
      </PageHeader>

      {/* A refresh that failed while figures are already on screen is a notice ABOVE them, not a
          page that replaces them: one missed poll during a deploy used to swap a working dashboard
          — tabs, range control and all — for an error card. */}
      {isError && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-xl bg-warning-500/15 px-3 py-2 text-xs text-warning-700"
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="min-w-0 flex-1">
            {t("dash.stale", { time: faTime(new Date(dataUpdatedAt).toISOString()) })}
          </span>
          <Button variant="ghost" size="xs" onClick={() => refetch()}>
            {t("ui.retry")}
          </Button>
        </div>
      )}

      {/* One panel for all seven tabs, named by whichever tab is selected — `role="tablist"` is a
          promise that something is being controlled, and until this existed nothing was. */}
      <div
        id={TAB_PANEL_ID}
        role="tabpanel"
        aria-labelledby={tabId(TAB_ID_BASE, tab)}
        className="space-y-4"
      >
        {/* A tab whose chart code is still downloading shows the same skeleton as its data would. */}
        <Suspense fallback={<TabSkeleton />}>
          {/* The overview is the redesigned screen: KPI band, activity trend, "top" cards and the live
          side rail. The other tabs keep the analytics panels built in Phase 2 — the design showed
          one screen, the product has six, and discarding five of them to match a mockup would be
          throwing away work the operator uses. */}
          {tab === "overview" && (
            <Overview
              stats={data}
              analytics={analytics}
              retention={retention}
              health={health}
              range={days}
              ranges={RANGES}
              onRange={setDays}
              pending={rangePending}
              onExport={exportCsv}
              exporting={exporting}
            />
          )}

          {tab === "growth" && (
            <>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <CumulativeUsersChart signups={data.signups_series} total={data.total_users} />
                <Analytic
                  {...analyticsState}
                  data={analytics}
                  render={(d) => <NewVsReturningChart data={d.new_vs_returning} />}
                />
              </div>
              <Analytic
                {...analyticsState}
                data={analytics}
                height="h-56"
                render={(d) => <ActiveUsersSeries data={d} />}
              />
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Analytic
                  {...analyticsState}
                  data={analytics}
                  render={(d) => <ActivationPanel data={d} />}
                />
                <ConversionPanel data={data} />
              </div>
            </>
          )}

          {tab === "retention" && (
            <>
              {retention ? (
                <RetentionCohorts data={retention} />
              ) : retentionQuery.isError ? (
                <ErrorState onRetry={() => void retentionQuery.refetch()} />
              ) : (
                <Card>
                  <Skeleton className="h-64 w-full" />
                </Card>
              )}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Analytic
                  {...analyticsState}
                  data={analytics}
                  render={(d) => <ActiveUsersPanel data={d} />}
                />
                <Analytic
                  {...analyticsState}
                  data={analytics}
                  render={(d) => <ClaimsDistribution data={d.claims_distribution} />}
                />
              </div>
            </>
          )}

          {tab === "referrals" && (
            <>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Analytic
                  {...analyticsState}
                  data={analytics}
                  render={(d) => <ReferralFunnelPanel data={d} />}
                />
                <Analytic
                  {...analyticsState}
                  data={analytics}
                  render={(d) => <ReferralCapPanel data={d} />}
                />
              </div>
              <TopReferrers data={data.top_referrers} />
            </>
          )}

          {tab === "usage" && (
            <Analytic
              data={usage}
              error={usageQuery.isError}
              onRetry={() => void usageQuery.refetch()}
              height="h-64"
              render={(d) => <UsagePanel data={d} />}
            />
          )}

          {tab === "geo" && (
            <>
              <Analytic
                {...analyticsState}
                data={analytics}
                height="h-64"
                render={(d) => <ActivityHeatmap cells={d.heatmap} />}
              />
              <Analytic
                {...analyticsState}
                data={analytics}
                height="h-64"
                render={(d) => (
                  <ActivityHeatmap
                    cells={d.signup_heatmap}
                    title={t("d.heat.signups")}
                    unit={t("d.heat.signupsUnit")}
                    axisNote={t("d.heat.signupsAxis")}
                  />
                )}
              />
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <TopLocations data={data.top_locations} total={data.locations_total} />
                <LanguageDonut data={data.languages} />
              </div>
              <Analytic
                {...analyticsState}
                data={analytics}
                render={(d) => <ReminderByLanguage data={d.reminder_by_language} />}
              />
            </>
          )}

          {tab === "health" && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <TrialHealthPanel data={data} />
              <ConversionPanel data={data} />
            </div>
          )}
        </Suspense>
      </div>
    </div>
  );
}

/** DAU as a trend rather than a single number — the dashboard only ever showed today's value. */
function ActiveUsersSeries({ data }: { data: DashboardAnalytics }) {
  const { t } = useI18n();
  const total = data.active_users_series.reduce((s, p) => s + p.count, 0);
  const peak = Math.max(1, ...data.active_users_series.map((p) => p.count));
  return (
    <Card>
      <CardHeader
        title={t("d.dau")}
        sub={t("d.dau.sub")}
        icon={Activity}
        action={<Badge tone="brand">{t("d.dau.peak", { n: formatNumber(peak) })}</Badge>}
      />
      {total === 0 ? (
        <EmptyState title={t("d.dau.empty")} />
      ) : (
        <div className="flex h-40 items-end gap-1" dir="ltr">
          {data.active_users_series.map((p) => (
            <div
              key={p.day}
              title={`${p.day}: ${formatNumber(p.count)}`}
              className="flex-1 rounded-t bg-brand/70 transition-colors hover:bg-brand"
              style={{ height: `${(p.count / peak) * 100}%`, minHeight: 2 }}
            />
          ))}
        </div>
      )}
    </Card>
  );
}

/** How many inviters have hit the configured reward ceiling and stopped earning. */
function ReferralCapPanel({ data }: { data: DashboardAnalytics }) {
  const { t } = useI18n();
  const { limit, at_cap, with_referrals } = data.referral_cap;
  const share = with_referrals ? (at_cap / with_referrals) * 100 : 0;
  return (
    <Card>
      <CardHeader
        title={t("d.cap")}
        sub={limit > 0 ? t("d.cap.current", { n: formatNumber(limit) }) : t("d.cap.none")}
        icon={Gift}
        action={<Badge tone={share > 50 ? "warning" : "neutral"}>{faPct(share)}</Badge>}
      />
      {with_referrals === 0 ? (
        <EmptyState title={t("d.cap.empty")} />
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-surface-raised p-3 text-center">
              <div className="text-xl font-bold tabular-nums text-content">
                {formatNumber(with_referrals)}
              </div>
              <div className="mt-0.5 text-xs text-content-muted">{t("d.cap.active")}</div>
            </div>
            <div className="rounded-xl bg-surface-raised p-3 text-center">
              <div className="text-xl font-bold tabular-nums text-content">
                {formatNumber(at_cap)}
              </div>
              <div className="mt-0.5 text-xs text-content-muted">{t("d.cap.atCap")}</div>
            </div>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
            <div className="h-full rounded-full bg-brand" style={{ width: `${share}%` }} />
          </div>
          <p className="text-xs text-content-muted">{t("d.cap.note")}</p>
        </div>
      )}
    </Card>
  );
}

function TabSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <Skeleton className="h-52 w-full" />
      </Card>
      <Card>
        <Skeleton className="h-52 w-full" />
      </Card>
    </div>
  );
}

function DashboardSkeleton() {
  const { t } = useI18n();
  return (
    <div className="space-y-4">
      <PageHeader title={t("dash.title")} />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Card key={i} className="flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-2xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-3 w-20" />
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <Skeleton className="mb-4 h-5 w-32" />
        <Skeleton className="h-64 w-full" />
      </Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <Skeleton className="h-56 w-full" />
        </Card>
        <Card>
          <Skeleton className="h-56 w-full" />
        </Card>
      </div>
    </div>
  );
}
