import { Cpu, Server } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardHeader } from "@/components/ui/Card";
import { useI18n } from "@/i18n";
import { faPct, formatNumber, humanBytes, humanUptime } from "@/lib/format";
import type { HostResources, PanelStats } from "@/types/api";

/** A ratio of two Latin quantities — one ltr run, or "2.8 GB / 7.5 GB" reverses in Persian. */
function Ratio({ a, b }: { a: string; b: string }) {
  return (
    <span dir="ltr" className="tabular-nums">
      {a} / {b}
    </span>
  );
}

function barColor(pct: number): string {
  if (pct >= 90) return "bg-danger";
  if (pct >= 75) return "bg-warning";
  return "bg-brand";
}

function Bar({ label, pct, hint }: { label: string; pct: number; hint?: ReactNode }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2 text-sm">
        <span className="text-content-muted">{label}</span>
        {/* The reading and the hint are SEPARATE flex items, not one inline run. Nested, the two
            numeric runs reordered into each other and «۳۷٫۵٪» + «2.8 GB / 7.5 GB» rendered as
            "GB / ۷٫۵ GB 37.5%۲٫۸" — a measurement no one can read. */}
        <span className="flex shrink-0 items-baseline gap-1.5">
          <b className="font-medium tabular-nums">{faPct(pct)}</b>
          {hint ? <span className="text-xs text-content-subtle">{hint}</span> : null}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
        <div
          className={`h-full rounded-full ${barColor(pct)} transition-all`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

export function GozarHostCard({ host }: { host: HostResources }) {
  const { t } = useI18n();
  // load average relative to cores → a rough CPU-pressure %.
  const loadPct = host.cpu_count ? Math.round((host.load1 / host.cpu_count) * 100) : 0;
  return (
    <Card>
      <CardHeader title={t("sys.host.bot")} icon={Server} />
      <div className="space-y-4">
        <Bar
          label={t("sys.host.cpu")}
          pct={Math.min(100, loadPct)}
          hint={t("sys.host.cpuHint", {
            load: formatNumber(host.load1),
            cores: formatNumber(host.cpu_count),
          })}
        />
        <Bar
          label={t("sys.host.mem")}
          pct={host.mem_pct}
          hint={<Ratio a={humanBytes(host.mem_used)} b={humanBytes(host.mem_total)} />}
        />
        <Bar
          label={t("sys.host.disk")}
          pct={host.disk_pct}
          hint={<Ratio a={humanBytes(host.disk_used)} b={humanBytes(host.disk_total)} />}
        />
        {/* The two figures live in ONE ltr run: «۰٫۵ · ۰٫۶» reordered to «۰٫۶ · ۰٫۵» under an
            RTL base direction, silently swapping the 5-minute and 15-minute readings. And they
            go through formatNumber, not localizeDigits — the latter maps digits but leaves an
            ASCII ".", so the load read «۰.۵» beside a «۳۷٫۵٪» on the same card. */}
        <div className="flex items-center gap-1.5 text-xs text-content-subtle">
          <span>{t("sys.host.loadRest")}</span>
          <span dir="ltr" className="tabular-nums">
            {formatNumber(host.load5)} · {formatNumber(host.load15)}
          </span>
        </div>
      </div>
    </Card>
  );
}

export function PanelHostCard({ panel }: { panel: PanelStats | null }) {
  const { t } = useI18n();
  const memPct =
    panel && panel.mem_total ? Math.round((panel.mem_used / panel.mem_total) * 100) : 0;
  return (
    <Card>
      <CardHeader title={t("sys.host.panel")} icon={Cpu} />
      {panel === null ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          {t("sys.host.panelDown")}
        </div>
      ) : (
        <div className="space-y-4">
          <Bar
            label={t("sys.host.mem")}
            pct={memPct}
            hint={<Ratio a={humanBytes(panel.mem_used)} b={humanBytes(panel.mem_total)} />}
          />
          <div className="grid grid-cols-2 gap-3 border-t border-line pt-3 text-center">
            <div>
              <div className="text-lg font-bold tabular-nums">{formatNumber(panel.cpu_cores)}</div>
              <div className="text-xs text-content-subtle">{t("sys.host.cores")}</div>
            </div>
            <div>
              <div className="text-lg font-bold tabular-nums">
                {humanUptime(panel.uptime_seconds)}
              </div>
              <div className="text-xs text-content-subtle">{t("sys.host.uptime")}</div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
