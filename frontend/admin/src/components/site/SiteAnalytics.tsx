import { BellRing, Gift, Globe, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { Section } from "@/components/ui/Section";
import { faPct, formatMb, formatNumber, langLabel } from "@/lib/format";
import type { AbuseSignals, PushHealth, RewardType, SiteAnalytics } from "@/types/api";

const REWARD_LABEL: Record<string, string> = {
  pwa: "نصب اپ (PWA)",
  push: "فعال‌کردن اعلان",
};

const STREAK_ORDER: { key: string; label: string }[] = [
  { key: "0", label: "بدون استریک" },
  { key: "1-2", label: "۱–۲ روز" },
  { key: "3-6", label: "۳–۶ روز" },
  { key: "7+", label: "۷+ روز" },
];

function Tile({ value, label, sub }: { value: number; label: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-surface-sunken p-3 text-center dark:bg-surface-sunken/50">
      <div className="text-xl font-bold tabular-nums">{formatNumber(value)}</div>
      <div className="mt-0.5 text-xs text-content-muted">{label}</div>
      {sub && (
        <div className="text-[10px] uppercase tracking-wide text-content-subtle" dir="ltr">
          {sub}
        </div>
      )}
    </div>
  );
}

function RewardEconomy({ items }: { items: RewardType[] }) {
  const totalMb = items.reduce((s, r) => s + r.total_mb, 0);
  return (
    <Card>
      <CardHeader
        title="اقتصاد پاداش"
        icon={Gift}
        action={<Badge tone="brand">مجموع {formatMb(totalMb)}</Badge>}
      />
      {items.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          هنوز پاداشی اعطا نشده
        </div>
      ) : (
        <ul className="space-y-2 text-sm">
          {items.map((r) => (
            <li
              key={r.type}
              className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-2 dark:bg-surface-sunken/50"
            >
              <span className="text-content-muted">{REWARD_LABEL[r.type] ?? r.type}</span>
              <span className="flex items-center gap-3 text-xs">
                <span className="text-content-subtle">{formatNumber(r.grants)} نفر</span>
                <span className="font-medium tabular-nums text-brand">{formatMb(r.total_mb)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-content-subtle">
        پاداش‌های یک‌بارهٔ ثبت‌شده (نصب اپ / اعلان). پاداش دعوت و استریک از شمارندهٔ دستگاه محاسبه
        می‌شوند.
      </p>
    </Card>
  );
}

function StreakPanel({ dist, active }: { dist: Record<string, number>; active: number }) {
  const rows = STREAK_ORDER.map((b) => ({ ...b, value: dist[b.key] ?? 0 }));
  const max = Math.max(1, ...rows.map((r) => r.value));
  const total = rows.reduce((s, r) => s + r.value, 0);
  return (
    <Card>
      <CardHeader
        title="استریک روزانه"
        icon={BellRing}
        action={<Badge tone="success">{formatNumber(active)} روی استریک فعال</Badge>}
      />
      {total === 0 ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          داده‌ای نیست
        </div>
      ) : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.key}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-content-muted">{r.label}</span>
                <span className="tabular-nums text-content-muted">{formatNumber(r.value)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
                <div
                  className="h-full rounded-full bg-brand transition-all"
                  style={{ width: `${(r.value / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function PushHealthPanel({ push }: { push: PushHealth }) {
  const total = push.active + push.inactive || 1;
  return (
    <Card>
      <CardHeader title="کانال اعلان (Web Push)" icon={Globe} />
      <div className="mb-3 flex gap-3">
        <Tile value={push.active} label="فعال" />
        <Tile value={push.inactive} label="غیرفعال / حذف‌شده" />
      </div>
      <div className="mb-3 flex h-2 overflow-hidden rounded-full bg-surface-sunken">
        <div className="h-full bg-brand" style={{ width: `${(push.active / total) * 100}%` }} />
      </div>
      {push.by_locale.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-medium text-content-muted">زبان مشترکین فعال:</div>
          <div className="flex flex-wrap gap-1.5">
            {push.by_locale.map((l) => (
              <span
                key={l.label}
                className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-content-muted"
              >
                {langLabel(l.label)} · {formatNumber(l.count)}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function AntiAbusePanel({ abuse }: { abuse: AbuseSignals }) {
  return (
    <Card>
      <CardHeader
        title="سیگنال‌های ضدتقلب"
        icon={ShieldAlert}
        action={
          abuse.shared_fingerprint_devices > 0 ? (
            <Badge tone="warning">
              {formatNumber(abuse.shared_fingerprint_devices)} دستگاه اثرانگشت مشترک
            </Badge>
          ) : (
            <Badge tone="success">پاک</Badge>
          )
        }
      />
      {abuse.top_ip_buckets.length === 0 ? (
        <div className="flex h-28 items-center justify-center text-center text-sm text-content-subtle">
          هیچ IP مشترکی بین چند دستگاه دیده نشد
        </div>
      ) : (
        <>
          <div className="mb-1.5 text-xs font-medium text-content-muted">
            IPهای پرتکرار (چند دستگاه پشت یک IP):
          </div>
          <ul className="space-y-1.5 text-sm">
            {abuse.top_ip_buckets.map((b) => (
              <li
                key={b.label}
                className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-1.5 dark:bg-surface-sunken/50"
              >
                <span className="font-mono text-xs text-content-muted" dir="ltr">
                  {b.label}
                </span>
                <span className="tabular-nums text-content-muted">
                  {formatNumber(b.count)} دستگاه
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="mt-3 text-xs text-content-subtle">
        این‌ها فقط نشانه‌اند، نه مسدودسازی خودکار — برای بررسی دستی.
      </p>
    </Card>
  );
}

/** The full deeper-analytics band for the website stats page. */
export function SiteAnalyticsSection({ data }: { data: SiteAnalytics }) {
  return (
    <>
      <Section
        title="کاربران فعال وب‌سایت"
        action={<Badge tone="brand">چسبندگی {faPct(data.stickiness_pct)}</Badge>}
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Tile value={data.dau} label="روزانه" sub="DAU" />
        <Tile value={data.wau} label="هفتگی" sub="WAU" />
        <Tile value={data.mau} label="ماهانه" sub="MAU" />
        <Tile
          value={data.devices_active_in_range}
          label={`فعال در ${formatNumber(data.range_days)} روز`}
        />
        <Tile
          value={data.claims_in_range}
          label={`دریافت در ${formatNumber(data.range_days)} روز`}
        />
      </div>

      {/* Everything below is LIFETIME, not windowed — say so, rather than letting the range
          buttons above imply otherwise. */}
      <Section title="اقتصاد پاداش و استریک" sub="ارقام کل دوره (بدون فیلتر بازه)" />
      <div className="grid gap-6 lg:grid-cols-2">
        <RewardEconomy items={data.reward_economy} />
        <StreakPanel dist={data.streak_distribution} active={data.active_streaks} />
      </div>

      <Section title="کانال اعلان و ضدتقلب" sub="ارقام کل دوره (بدون فیلتر بازه)" />
      <div className="grid gap-6 lg:grid-cols-2">
        <PushHealthPanel push={data.push} />
        <AntiAbusePanel abuse={data.abuse} />
      </div>
    </>
  );
}
