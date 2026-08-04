import {
  BellRing,
  Download,
  ExternalLink,
  FileText,
  Globe,
  Inbox,
  MonitorSmartphone,
  Wrench,
} from "lucide-react";
import { type ReactNode } from "react";
import { Link } from "react-router-dom";

import { StatCard } from "@/components/dashboard/StatCard";
import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  useSiteLandingPages,
  useSitePushHistory,
  useSiteSettings,
  useSiteStats,
  useSiteUnreadCount,
} from "@/hooks/useSite";
import { useI18n } from "@/i18n";
import { faDate, faPct, formatMb, formatNumber } from "@/lib/format";

/**
 * The website section's front door.
 *
 * Everything here already existed in some endpoint; what was missing was one screen that says "is
 * the site set up, is anything waiting for me, and where do I go". Composed entirely from the
 * existing queries — no new backend surface.
 */
const RANGE_DAYS = 14;

export function SiteOverview() {
  const { t } = useI18n();
  const { data: settings, isLoading: settingsLoading } = useSiteSettings();
  const { data: stats } = useSiteStats(RANGE_DAYS);
  const { data: pages } = useSiteLandingPages();
  const { data: unread } = useSiteUnreadCount();
  const { data: pushHistory } = useSitePushHistory();

  const configured = Boolean(settings?.trial_squad);
  const lastPush = pushHistory?.[0];
  const publishedPages = (pages ?? []).filter((p) => p.published).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("so.title")}
        sub={t("so.sub")}
        actions={
          <a href="/" target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm">
              <ExternalLink className="h-4 w-4" />
              {t("so.visit")}
            </Button>
          </a>
        }
      >
        <SiteTabs unreadMessages={unread} />
      </PageHeader>

      {settingsLoading ? (
        <Card>
          <Skeleton className="h-24 w-full" />
        </Card>
      ) : !configured ? (
        <Card>
          <EmptyState
            icon={Wrench}
            title={t("so.notSetUp")}
            message={t("so.notSetUp.msg")}
            action={
              <Link to="/site/setup">
                <Button>{t("so.setUpNow")}</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {/* Windowed, matching the 14-day query above — the overview used to show the all-time
                identity count under the word "visitors", which only ever grows. */}
            <StatCard
              label={t("so.kpi.visitors", { days: formatNumber(RANGE_DAYS) })}
              value={formatNumber(stats?.visitors.value ?? 0)}
              icon={Globe}
              tone="brand"
              delta={stats?.visitors.change_pct}
            />
            <StatCard
              label={t("so.kpi.claimers", { days: formatNumber(RANGE_DAYS) })}
              value={formatNumber(stats?.claimers.value ?? 0)}
              icon={Download}
              tone="success"
              delta={stats?.claimers.change_pct}
              hint={t("so.kpi.conversion", { pct: faPct(stats?.conversion_pct ?? 0) })}
            />
            <StatCard
              label={t("so.kpi.subscribers")}
              value={formatNumber(stats?.push_subscribers ?? 0)}
              icon={BellRing}
              tone="warning"
            />
            <StatCard
              label={t("so.kpi.unread")}
              value={formatNumber(unread ?? 0)}
              icon={Inbox}
              tone={unread ? "danger" : "neutral"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title={t("so.config")} icon={Wrench} />
              <div>
                <Row
                  label={t("so.config.locations")}
                  value={
                    settings && settings.locations.length > 0
                      ? t("so.config.locationsN", { n: formatNumber(settings.locations.length) })
                      : t("so.config.locationsAll")
                  }
                />
                <Row label={t("so.config.popular")} value={settings?.popular_location || "—"} />
                <Row
                  label={t("so.config.daily")}
                  value={settings ? formatMb(settings.daily_limit_mb) : "—"}
                />
                <Row
                  label={t("so.config.trial")}
                  value={
                    settings ? t("so.config.hours", { n: formatNumber(settings.trial_hours) }) : "—"
                  }
                />
                <Row
                  label={t("so.config.reward")}
                  value={settings ? formatMb(settings.referral_reward_mb) : "—"}
                />
              </div>
              <div className="mt-4 flex gap-2">
                <Link to="/site/settings">
                  <Button variant="outline" size="sm">
                    {t("so.config.editSettings")}
                  </Button>
                </Link>
                <Link to="/site/content">
                  <Button variant="ghost" size="sm">
                    {t("so.config.editCopy")}
                  </Button>
                </Link>
              </div>
            </Card>

            <Card>
              <CardHeader title={t("so.reach")} icon={FileText} />
              <div>
                <Row
                  label={t("so.reach.pages")}
                  value={t("so.reach.pagesOf", {
                    n: formatNumber(publishedPages),
                    total: formatNumber(pages?.length ?? 0),
                  })}
                />
                <Row
                  label={t("so.reach.lastPush")}
                  value={
                    lastPush ? (
                      <span className="flex items-center gap-2">
                        {faDate(lastPush.created_at)}
                        <Badge tone={lastPush.status === "done" ? "success" : "neutral"}>
                          {lastPush.status === "done"
                            ? t("so.reach.delivered", { n: formatNumber(lastPush.sent) })
                            : lastPush.status}
                        </Badge>
                      </span>
                    ) : (
                      t("so.reach.noPush")
                    )
                  }
                />
                <Row
                  label={t("so.reach.activeConfigs")}
                  value={
                    <span className="flex items-center gap-2">
                      {formatNumber(stats?.active_configs_live ?? 0)}
                      {(stats?.active_configs_stale ?? 0) > 0 && (
                        <Badge tone="warning">
                          {t("so.reach.stale", {
                            n: formatNumber(stats?.active_configs_stale ?? 0),
                          })}
                        </Badge>
                      )}
                    </span>
                  }
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/site/pages">
                  <Button variant="outline" size="sm">
                    <FileText className="h-4 w-4" />
                    {t("so.link.pages")}
                  </Button>
                </Link>
                <Link to="/site/inbox">
                  <Button variant="ghost" size="sm">
                    <Inbox className="h-4 w-4" />
                    {t("so.link.inbox")}
                  </Button>
                </Link>
                <Link to="/site/devices">
                  <Button variant="ghost" size="sm">
                    <MonitorSmartphone className="h-4 w-4" />
                    {t("so.link.devices")}
                  </Button>
                </Link>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line py-2 text-sm last:border-0">
      <span className="text-content-muted">{label}</span>
      <span className="text-content">{value}</span>
    </div>
  );
}
