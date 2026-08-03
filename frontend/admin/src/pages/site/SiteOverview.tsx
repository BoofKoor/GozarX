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
import { faDate, faPct, formatMb, formatNumber } from "@/lib/format";

/**
 * The website section's front door.
 *
 * Everything here already existed in some endpoint; what was missing was one screen that says "is
 * the site set up, is anything waiting for me, and where do I go". Composed entirely from the
 * existing queries — no new backend surface.
 */
export function SiteOverview() {
  const { data: settings, isLoading: settingsLoading } = useSiteSettings();
  const { data: stats } = useSiteStats(14);
  const { data: pages } = useSiteLandingPages();
  const { data: unread } = useSiteUnreadCount();
  const { data: pushHistory } = useSitePushHistory();

  const configured = Boolean(settings?.trial_squad);
  const lastPush = pushHistory?.[0];
  const publishedPages = (pages ?? []).filter((p) => p.published).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="نمای کلی وب‌سایت"
        sub="وضعیت سایت عمومی در یک نگاه."
        actions={
          <a href="/" target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm">
              <ExternalLink className="h-4 w-4" />
              مشاهدهٔ سایت
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
            title="وب‌سایت هنوز راه‌اندازی نشده است"
            message="تا وقتی اسکواد آزمایشی تنظیم نشود، سایت عمومی نمی‌تواند کانفیگ بدهد."
            action={
              <Link to="/site/setup">
                <Button>راه‌اندازی وب‌سایت</Button>
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
              label="بازدیدکننده (۱۴ روز)"
              value={formatNumber(stats?.visitors.value ?? 0)}
              icon={Globe}
              tone="brand"
              delta={stats?.visitors.change_pct}
            />
            <StatCard
              label="دریافت‌کننده (۱۴ روز)"
              value={formatNumber(stats?.claimers.value ?? 0)}
              icon={Download}
              tone="success"
              delta={stats?.claimers.change_pct}
              hint={`نرخ تبدیل: ${faPct(stats?.conversion_pct ?? 0)}`}
            />
            <StatCard
              label="مشترک اعلان"
              value={formatNumber(stats?.push_subscribers ?? 0)}
              icon={BellRing}
              tone="warning"
            />
            <StatCard
              label="پیام خوانده‌نشده"
              value={formatNumber(unread ?? 0)}
              icon={Inbox}
              tone={unread ? "danger" : "neutral"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="پیکربندی فعلی" icon={Wrench} />
              <div>
                <Row
                  label="لوکیشن‌های ارائه‌شده"
                  value={
                    settings && settings.locations.length > 0
                      ? `${formatNumber(settings.locations.length)} لوکیشن`
                      : "همهٔ لوکیشن‌های اسکواد"
                  }
                />
                <Row label="لوکیشن محبوب" value={settings?.popular_location || "—"} />
                <Row
                  label="حجم روزانه"
                  value={settings ? formatMb(settings.daily_limit_mb) : "—"}
                />
                <Row
                  label="مدت اعتبار کانفیگ"
                  value={settings ? `${formatNumber(settings.trial_hours)} ساعت` : "—"}
                />
                <Row
                  label="پاداش هر دعوت"
                  value={settings ? formatMb(settings.referral_reward_mb) : "—"}
                />
              </div>
              <div className="mt-4 flex gap-2">
                <Link to="/site/settings">
                  <Button variant="outline" size="sm">
                    ویرایش تنظیمات
                  </Button>
                </Link>
                <Link to="/site/content">
                  <Button variant="ghost" size="sm">
                    ویرایش محتوا
                  </Button>
                </Link>
              </div>
            </Card>

            <Card>
              <CardHeader title="محتوا و ارتباط" icon={FileText} />
              <div>
                <Row
                  label="صفحه‌های فرود منتشرشده"
                  value={`${formatNumber(publishedPages)} از ${formatNumber(pages?.length ?? 0)}`}
                />
                <Row
                  label="آخرین اعلان"
                  value={
                    lastPush ? (
                      <span className="flex items-center gap-2">
                        {faDate(lastPush.created_at)}
                        <Badge tone={lastPush.status === "done" ? "success" : "neutral"}>
                          {lastPush.status === "done"
                            ? `${formatNumber(lastPush.sent)} تحویل`
                            : lastPush.status}
                        </Badge>
                      </span>
                    ) : (
                      "هنوز ارسال نشده"
                    )
                  }
                />
                <Row
                  label="کانفیگ فعال روی سایت"
                  value={
                    <span className="flex items-center gap-2">
                      {formatNumber(stats?.active_configs_live ?? 0)}
                      {(stats?.active_configs_stale ?? 0) > 0 && (
                        <Badge tone="warning">
                          {formatNumber(stats?.active_configs_stale ?? 0)} هم‌گام‌نشده
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
                    صفحه‌ها
                  </Button>
                </Link>
                <Link to="/site/inbox">
                  <Button variant="ghost" size="sm">
                    <Inbox className="h-4 w-4" />
                    پیام‌ها
                  </Button>
                </Link>
                <Link to="/site/devices">
                  <Button variant="ghost" size="sm">
                    <MonitorSmartphone className="h-4 w-4" />
                    دستگاه‌ها
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
