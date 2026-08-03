import { BellRing, Download, Globe, Zap } from "lucide-react";
import { useState } from "react";

import { StatCard } from "@/components/dashboard/StatCard";
import { SiteAnalyticsSection } from "@/components/site/SiteAnalytics";
import { SiteTabs } from "@/components/site/SiteTabs";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Section } from "@/components/ui/Section";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useSiteAnalytics, useSiteStats } from "@/hooks/useSite";
import { faPct, formatNumber, shortDay } from "@/lib/format";

const RANGE_OPTIONS = [7, 14, 30, 90].map((r) => ({ value: r, label: `${formatNumber(r)} روز` }));

const STATUS_LABEL: Record<string, string> = {
  available: "آزاد",
  active_config: "دارای کانفیگ",
  blocked: "مسدود",
};

export function SiteStats() {
  const [days, setDays] = useState(14);
  const { data, isError, refetch } = useSiteStats(days);
  // Same window as the funnel above — the range control now moves the WHOLE page.
  const { data: analytics } = useSiteAnalytics(days);

  const topMax = data ? Math.max(1, ...data.top_locations.map((l) => l.count)) : 1;
  const claimsMax = data ? Math.max(1, ...data.claims_series.map((d) => d.count)) : 1;

  return (
    <div className="space-y-6">
      <PageHeader
        title="آمار وب‌سایت"
        sub="قیف بازدید تا دریافت کانفیگ، و تحلیل عمیق‌تر رفتار بازدیدکننده‌ها."
        actions={
          <Segmented
            value={days}
            onChange={setDays}
            options={RANGE_OPTIONS}
            size="sm"
            ariaLabel="بازهٔ زمانی"
          />
        }
      >
        <SiteTabs />
      </PageHeader>

      {!data ? (
        isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : (
          <div className="flex justify-center py-20">
            <Spinner className="h-8 w-8 text-brand" />
          </div>
        )
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="دستگاه‌ها (بازدید)"
              value={formatNumber(data.total_devices)}
              icon={Globe}
            />
            <StatCard
              label="دریافت‌کننده‌ها"
              value={formatNumber(data.devices_claimed)}
              icon={Download}
              tone="success"
              hint={`نرخ تبدیل: ${faPct(data.conversion_pct)}`}
            />
            <StatCard
              label="کانفیگ فعال"
              value={formatNumber(data.active_configs)}
              icon={Zap}
              tone="info"
            />
            <StatCard
              label="دریافت امروز"
              value={formatNumber(data.configs_today)}
              icon={Download}
              tone="brand"
            />
            <StatCard
              label="مشترک اعلان"
              value={formatNumber(data.push_subscribers)}
              icon={BellRing}
              tone="warning"
            />
          </div>

          <Card>
            <h3 className="mb-3 text-sm font-bold text-content-muted">
              دریافت روزانه ({formatNumber(days)} روز اخیر)
            </h3>
            {data.claims_series.length === 0 ? (
              <p className="py-4 text-center text-sm text-content-subtle">داده‌ای نیست.</p>
            ) : (
              <div className="flex h-24 items-end gap-1" dir="ltr">
                {data.claims_series.map((d) => (
                  <div
                    key={d.day}
                    title={`${shortDay(d.day)}: ${formatNumber(d.count)}`}
                    className="flex-1 rounded-t bg-brand/70 transition-colors hover:bg-brand"
                    style={{ height: `${(d.count / claimsMax) * 100}%`, minHeight: 2 }}
                  />
                ))}
              </div>
            )}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h3 className="mb-3 text-sm font-bold text-content-muted">
                پرطرفدارترین لوکیشن‌ها ({formatNumber(days)} روز اخیر)
              </h3>
              {data.top_locations.length === 0 ? (
                <p className="py-4 text-center text-sm text-content-subtle">داده‌ای نیست.</p>
              ) : (
                <ul className="space-y-2">
                  {data.top_locations.map((l) => (
                    <li key={l.label}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span dir="auto">{l.label}</span>
                        <span className="tabular-nums text-content-muted">
                          {formatNumber(l.count)}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-surface-sunken">
                        <div
                          className="h-2 rounded-full bg-brand"
                          style={{ width: `${(l.count / topMax) * 100}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card>
              <h3 className="mb-3 text-sm font-bold text-content-muted">وضعیت دستگاه‌ها</h3>
              <ul className="space-y-2 text-sm">
                {Object.entries(data.status_counts).map(([status, count]) => (
                  <li key={status} className="flex justify-between">
                    <span>{STATUS_LABEL[status] ?? status}</span>
                    <span className="tabular-nums text-content-muted">{formatNumber(count)}</span>
                  </li>
                ))}
                {Object.keys(data.status_counts).length === 0 && (
                  <li className="py-4 text-center text-content-subtle">داده‌ای نیست.</li>
                )}
              </ul>
            </Card>
          </div>

          {analytics ? (
            <SiteAnalyticsSection data={analytics} />
          ) : (
            <>
              <Section title="تحلیل عمیق وب‌سایت" />
              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <Skeleton className="h-40 w-full" />
                </Card>
                <Card>
                  <Skeleton className="h-40 w-full" />
                </Card>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
