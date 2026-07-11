import { clsx } from "clsx";
import { BellRing, Download, Globe, Zap } from "lucide-react";
import { useState } from "react";

import { StatCard } from "@/components/dashboard/StatCard";
import { SiteTabs } from "@/components/site/SiteTabs";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useSiteStats } from "@/hooks/useSite";

const RANGES = [7, 14, 30];

const STATUS_LABEL: Record<string, string> = {
  available: "آزاد",
  active_config: "دارای کانفیگ",
  blocked: "مسدود",
};

export function SiteStats() {
  const [days, setDays] = useState(14);
  const { data, isLoading } = useSiteStats(days);

  const topMax = data ? Math.max(1, ...data.top_locations.map((l) => l.count)) : 1;
  const claimsMax = data ? Math.max(1, ...data.claims_series.map((d) => d.count)) : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">وب‌سایت</h1>
      <SiteTabs />

      <div className="flex gap-1">
        {RANGES.map((r) => (
          <button
            key={r}
            onClick={() => setDays(r)}
            className={clsx(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              r === days
                ? "bg-brand/10 text-brand"
                : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800",
            )}
          >
            {r} روز
          </button>
        ))}
      </div>

      {isLoading || !data ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8 text-brand" />
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard label="دستگاه‌ها (بازدید)" value={data.total_devices} icon={Globe} />
            <StatCard
              label="دریافت‌کننده‌ها"
              value={data.devices_claimed}
              icon={Download}
              tone="success"
              hint={`نرخ تبدیل: ${data.conversion_pct}٪`}
            />
            <StatCard label="کانفیگ فعال" value={data.active_configs} icon={Zap} tone="info" />
            <StatCard label="دریافت امروز" value={data.configs_today} icon={Download} tone="brand" />
            <StatCard
              label="مشترک اعلان"
              value={data.push_subscribers}
              icon={BellRing}
              tone="warning"
            />
          </div>

          <Card>
            <h3 className="mb-3 text-sm font-bold text-slate-600 dark:text-slate-300">
              دریافت روزانه ({days} روز اخیر)
            </h3>
            {data.claims_series.length === 0 ? (
              <p className="py-4 text-center text-sm text-slate-400">داده‌ای نیست.</p>
            ) : (
              <div className="flex h-24 items-end gap-1" dir="ltr">
                {data.claims_series.map((d) => (
                  <div
                    key={d.day}
                    title={`${d.day}: ${d.count}`}
                    className="flex-1 rounded-t bg-brand/70"
                    style={{ height: `${(d.count / claimsMax) * 100}%`, minHeight: 2 }}
                  />
                ))}
              </div>
            )}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h3 className="mb-3 text-sm font-bold text-slate-600 dark:text-slate-300">
                پرطرفدارترین لوکیشن‌ها ({days} روز اخیر)
              </h3>
              {data.top_locations.length === 0 ? (
                <p className="py-4 text-center text-sm text-slate-400">داده‌ای نیست.</p>
              ) : (
                <ul className="space-y-2">
                  {data.top_locations.map((l) => (
                    <li key={l.label}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span dir="auto">{l.label}</span>
                        <span className="tabular-nums text-slate-500">{l.count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800">
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
              <h3 className="mb-3 text-sm font-bold text-slate-600 dark:text-slate-300">
                وضعیت دستگاه‌ها
              </h3>
              <ul className="space-y-2 text-sm">
                {Object.entries(data.status_counts).map(([status, count]) => (
                  <li key={status} className="flex justify-between">
                    <span>{STATUS_LABEL[status] ?? status}</span>
                    <span className="tabular-nums text-slate-500">{count}</span>
                  </li>
                ))}
                {Object.keys(data.status_counts).length === 0 && (
                  <li className="py-4 text-center text-slate-400">داده‌ای نیست.</li>
                )}
              </ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
