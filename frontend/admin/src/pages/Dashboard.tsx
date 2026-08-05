import {
  Activity,
  Download,
  Gift,
  Globe2,
  HeartPulse,
  LineChart,
  Repeat,
  UserPlus,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ActivationPanel } from "@/components/dashboard/ActivationPanel";
import { ActiveUsersPanel } from "@/components/dashboard/ActiveUsersPanel";
import { ActivityHeatmap } from "@/components/dashboard/ActivityHeatmap";
import { ClaimsDistribution } from "@/components/dashboard/ClaimsDistribution";
import { ConversionPanel } from "@/components/dashboard/ConversionPanel";
import { CumulativeUsersChart } from "@/components/dashboard/CumulativeUsersChart";
import { LanguageDonut } from "@/components/dashboard/LanguageDonut";
import { NewVsReturningChart } from "@/components/dashboard/NewVsReturningChart";
import { ReferralFunnelPanel } from "@/components/dashboard/ReferralFunnelPanel";
import { ReminderByLanguage } from "@/components/dashboard/ReminderByLanguage";
import { RetentionCohorts } from "@/components/dashboard/RetentionCohorts";
import { Overview } from "@/components/dashboard/overview/Overview";
import { TopLocations } from "@/components/dashboard/TopLocations";
import { TopReferrers } from "@/components/dashboard/TopReferrers";
import { TrialHealthPanel } from "@/components/dashboard/TrialHealthPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import { useSystemHealth } from "@/hooks/useSystem";
import {
  RANGES,
  downloadDashboardCsv,
  useDashboard,
  useDashboardAnalytics,
  useRetention,
} from "@/hooks/useDashboard";
import { useI18n, type MessageKey } from "@/i18n";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

type TabKey = "overview" | "growth" | "retention" | "referrals" | "geo" | "health";

const TAB_KEYS: { value: TabKey; labelKey: MessageKey; icon: typeof LineChart }[] = [
  { value: "overview", labelKey: "dash.tab.overview", icon: LineChart },
  { value: "growth", labelKey: "dash.tab.growth", icon: UserPlus },
  { value: "retention", labelKey: "dash.tab.retention", icon: Repeat },
  { value: "referrals", labelKey: "dash.tab.referrals", icon: Gift },
  { value: "geo", labelKey: "dash.tab.geo", icon: Globe2 },
  { value: "health", labelKey: "dash.tab.health", icon: HeartPulse },
];

// Built per render rather than at module scope: the label is localized, so a constant would
// freeze whichever language happened to load first.
const RANGE_VALUES = RANGES as readonly number[];

/** Render an analytics panel once its (separate) query has loaded, else a stable skeleton so the
 *  grid doesn't jump when the deeper stats arrive a moment after the headline. */
function Analytic({
  data,
  render,
  height = "h-52",
}: {
  data: DashboardAnalytics | undefined;
  render: (d: DashboardAnalytics) => JSX.Element;
  height?: string;
}) {
  if (!data) {
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
  const [tab, setTab] = useState<TabKey>("overview");
  const [exporting, setExporting] = useState(false);
  const { data, isLoading, isError, refetch } = useDashboard(days);
  // Every windowed panel reads from these two queries, so the range control drives the WHOLE page —
  // it used to move only the activity chart while the panels beside it stayed on their own window.
  const { data: analytics } = useDashboardAnalytics(days);
  // Cohorts are inherently weekly, so they keep their own axis rather than the day range.
  const { data: retention } = useRetention(8);

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

  if (isLoading) {
    return <DashboardSkeleton />;
  }
  if (isError || !data) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("dash.title")} />
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
              <Segmented
                value={days}
                onChange={setDays}
                options={RANGE_OPTIONS}
                size="sm"
                ariaLabel={t("dash.range.aria")}
              />
              <Button variant="outline" size="sm" onClick={exportCsv} loading={exporting}>
                <Download className="h-4 w-4" />
                <span className="hidden sm:inline">{t("dash.export")}</span>
              </Button>
            </>
          )
        }
      >
        <Tabs value={tab} onChange={setTab} items={TABS} />
      </PageHeader>

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
          range={data.range_days}
          ranges={RANGES}
          onRange={setDays}
          onExport={exportCsv}
          exporting={exporting}
        />
      )}

      {tab === "growth" && (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <CumulativeUsersChart signups={data.signups_series} total={data.total_users} />
            <Analytic
              data={analytics}
              render={(d) => <NewVsReturningChart data={d.new_vs_returning} />}
            />
          </div>
          <Analytic data={analytics} height="h-56" render={(d) => <ActiveUsersSeries data={d} />} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ActivationPanel data={d} />} />
            <ConversionPanel data={data} />
          </div>
        </>
      )}

      {tab === "retention" && (
        <>
          {retention ? (
            <RetentionCohorts data={retention} />
          ) : (
            <Card>
              <Skeleton className="h-64 w-full" />
            </Card>
          )}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ActiveUsersPanel data={d} />} />
            <Analytic
              data={analytics}
              render={(d) => <ClaimsDistribution data={d.claims_distribution} />}
            />
          </div>
        </>
      )}

      {tab === "referrals" && (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ReferralFunnelPanel data={d} />} />
            <Analytic data={analytics} render={(d) => <ReferralCapPanel data={d} />} />
          </div>
          <TopReferrers data={data.top_referrers} />
        </>
      )}

      {tab === "geo" && (
        <>
          <Analytic
            data={analytics}
            height="h-64"
            render={(d) => <ActivityHeatmap cells={d.heatmap} />}
          />
          <Analytic
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
            <TopLocations data={data.top_locations} />
            <LanguageDonut data={data.languages} />
          </div>
          <Analytic
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
