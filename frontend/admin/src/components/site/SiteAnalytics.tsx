import { BellRing, ChevronLeft, Gift, Globe, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { Section } from "@/components/ui/Section";
import { useI18n, type MessageKey } from "@/i18n";
import { faPct, formatMb, formatNumber, langLabel } from "@/lib/format";
import type { AbuseSignals, PushHealth, RewardType, SiteAnalytics } from "@/types/api";

const REWARD_LABEL: Record<string, MessageKey> = {
  pwa: "sa.reward.pwa",
  push: "sa.reward.push",
};

const STREAK_ORDER: { key: string; label: MessageKey }[] = [
  { key: "0", label: "sa.streak.0" },
  { key: "1-2", label: "sa.streak.1-2" },
  { key: "3-6", label: "sa.streak.3-6" },
  { key: "7+", label: "sa.streak.7+" },
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
  const { t } = useI18n();
  const totalMb = items.reduce((s, r) => s + r.total_mb, 0);
  return (
    <Card>
      <CardHeader
        title={t("sa.rewards")}
        icon={Gift}
        action={<Badge tone="brand">{t("sa.rewards.total", { mb: formatMb(totalMb) })}</Badge>}
      />
      {items.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          {t("sa.rewards.empty")}
        </div>
      ) : (
        <ul className="space-y-2 text-sm">
          {items.map((r) => (
            <li
              key={r.type}
              className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-2 dark:bg-surface-sunken/50"
            >
              <span className="text-content-muted">
                {REWARD_LABEL[r.type] ? t(REWARD_LABEL[r.type]) : r.type}
              </span>
              <span className="flex items-center gap-3 text-xs">
                <span className="text-content-subtle">
                  {t("sa.rewards.people", { n: formatNumber(r.grants) })}
                </span>
                <span className="font-medium tabular-nums text-brand">{formatMb(r.total_mb)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-content-subtle">{t("sa.rewards.note")}</p>
    </Card>
  );
}

function StreakPanel({ dist, active }: { dist: Record<string, number>; active: number }) {
  const { t } = useI18n();
  const rows = STREAK_ORDER.map((b) => ({ ...b, value: dist[b.key] ?? 0 }));
  const max = Math.max(1, ...rows.map((r) => r.value));
  const total = rows.reduce((s, r) => s + r.value, 0);
  return (
    <Card>
      <CardHeader
        title={t("sa.streak")}
        icon={BellRing}
        action={<Badge tone="success">{t("sa.streak.active", { n: formatNumber(active) })}</Badge>}
      />
      {total === 0 ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          {t("sa.streak.empty")}
        </div>
      ) : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.key}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-content-muted">{t(r.label)}</span>
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
  const { t } = useI18n();
  const total = push.active + push.inactive || 1;
  return (
    <Card>
      <CardHeader title={t("sa.push")} icon={Globe} />
      <div className="mb-3 flex gap-3">
        <Tile value={push.active} label={t("sa.push.active")} />
        <Tile value={push.inactive} label={t("sa.push.inactive")} />
      </div>
      <div className="mb-3 flex h-2 overflow-hidden rounded-full bg-surface-sunken">
        <div className="h-full bg-brand" style={{ width: `${(push.active / total) * 100}%` }} />
      </div>
      {push.by_locale.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-medium text-content-muted">
            {t("sa.push.byLocale")}
          </div>
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
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader
        title={t("sa.abuse")}
        icon={ShieldAlert}
        action={
          abuse.shared_fingerprint_devices > 0 ? (
            <Badge tone="warning">
              {t("sa.abuse.sharedFp", { n: formatNumber(abuse.shared_fingerprint_devices) })}
            </Badge>
          ) : (
            <Badge tone="success">{t("sa.abuse.clean")}</Badge>
          )
        }
      />
      {abuse.top_ip_buckets.length === 0 ? (
        <div className="flex h-28 items-center justify-center text-center text-sm text-content-subtle">
          {t("sa.abuse.noIp")}
        </div>
      ) : (
        <>
          <div className="mb-1.5 text-xs font-medium text-content-muted">
            {t("sa.abuse.busyIps")}
          </div>
          <ul className="space-y-1.5 text-sm">
            {abuse.top_ip_buckets.map((b) => (
              <li key={b.label}>
                {/* The panel used to name a bucket and stop there. This opens the actual devices
                    behind it, which is the only thing that makes the signal actionable. */}
                <Link
                  to={`/site/devices?ip_bucket=${encodeURIComponent(b.label)}`}
                  className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-1.5 transition hover:bg-surface-hover"
                >
                  <span className="font-mono text-xs text-content-muted" dir="ltr">
                    {b.label}
                  </span>
                  <span className="flex items-center gap-1 tabular-nums text-content-muted">
                    {t("sa.abuse.devices", { n: formatNumber(b.count) })}
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="mt-3 text-xs text-content-subtle">{t("sa.abuse.note")}</p>
    </Card>
  );
}

/** The full deeper-analytics band for the website stats page. */
export function SiteAnalyticsSection({ data }: { data: SiteAnalytics }) {
  const { t } = useI18n();
  return (
    <>
      {/* Two different questions, and the panel used to answer only the second one. "Seen" counts
          every device that visited; "claimed" counts only those that provisioned — so a visitor who
          reads the page and leaves was previously invisible in every activity number. */}
      <Section
        title={t("sa.visitors")}
        sub={t("sa.visitors.sub")}
        action={
          <Badge tone="brand">
            {t("sa.stickiness", { pct: faPct(data.visit_stickiness_pct) })}
          </Badge>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile value={data.visitors_24h} label={t("sa.range.24h")} sub="DAU" />
        <Tile value={data.visitors_7d} label={t("sa.range.7d")} sub="WAU" />
        <Tile value={data.visitors_30d} label={t("sa.range.30d")} sub="MAU" />
        <Tile
          value={data.claims_in_range}
          label={t("sa.claimsInRange", { n: formatNumber(data.range_days) })}
        />
      </div>

      <Section
        title={t("sa.claimers")}
        sub={t("sa.claimers.sub")}
        action={
          <Badge tone="success">{t("sa.stickiness", { pct: faPct(data.stickiness_pct) })}</Badge>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile value={data.dau} label={t("sa.daily")} sub="DAU" />
        <Tile value={data.wau} label={t("sa.weekly")} sub="WAU" />
        <Tile value={data.mau} label={t("sa.monthly")} sub="MAU" />
        <Tile
          value={data.devices_active_in_range}
          label={t("sa.activeInRange", { n: formatNumber(data.range_days) })}
        />
      </div>

      {/* Everything below is LIFETIME, not windowed — say so, rather than letting the range
          buttons above imply otherwise. */}
      <Section title={t("sa.section.rewards")} sub={t("sa.section.allTime")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <RewardEconomy items={data.reward_economy} />
        <StreakPanel dist={data.streak_distribution} active={data.active_streaks} />
      </div>

      <Section title={t("sa.section.push")} sub={t("sa.section.allTime")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <PushHealthPanel push={data.push} />
        <AntiAbusePanel abuse={data.abuse} />
      </div>
    </>
  );
}
