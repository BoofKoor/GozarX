import { Cpu, Server } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { humanBytes, humanUptime } from "@/lib/format";
import type { HostResources, PanelStats } from "@/types/api";

function barColor(pct: number): string {
  if (pct >= 90) return "bg-danger";
  if (pct >= 75) return "bg-warning";
  return "bg-brand";
}

function Bar({ label, pct, hint }: { label: string; pct: number; hint?: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-content-muted">{label}</span>
        <span className="font-medium tabular-nums">
          {pct}%{hint ? <span className="ms-1 text-xs text-content-subtle">{hint}</span> : null}
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
  // load average relative to cores → a rough CPU-pressure %.
  const loadPct = host.cpu_count ? Math.round((host.load1 / host.cpu_count) * 100) : 0;
  return (
    <Card>
      <CardHeader title="منابع سرور ربات" icon={Server} />
      <div className="space-y-4">
        <Bar
          label="بار پردازنده (۱ دقیقه)"
          pct={Math.min(100, loadPct)}
          hint={`${host.load1} از ${host.cpu_count} هسته`}
        />
        <Bar
          label="حافظه"
          pct={host.mem_pct}
          hint={`${humanBytes(host.mem_used)} / ${humanBytes(host.mem_total)}`}
        />
        <Bar
          label="دیسک"
          pct={host.disk_pct}
          hint={`${humanBytes(host.disk_used)} / ${humanBytes(host.disk_total)}`}
        />
        <div className="text-xs text-content-subtle">
          بار ۵ و ۱۵ دقیقه: {host.load5} · {host.load15}
        </div>
      </div>
    </Card>
  );
}

export function PanelHostCard({ panel }: { panel: PanelStats | null }) {
  const memPct =
    panel && panel.mem_total ? Math.round((panel.mem_used / panel.mem_total) * 100) : 0;
  return (
    <Card>
      <CardHeader title="منابع سرور پنل" icon={Cpu} />
      {panel === null ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          پنل در دسترس نیست
        </div>
      ) : (
        <div className="space-y-4">
          <Bar
            label="حافظه"
            pct={memPct}
            hint={`${humanBytes(panel.mem_used)} / ${humanBytes(panel.mem_total)}`}
          />
          <div className="grid grid-cols-2 gap-3 border-t border-line pt-3 text-center">
            <div>
              <div className="text-lg font-bold tabular-nums">{panel.cpu_cores}</div>
              <div className="text-xs text-content-subtle">هسته پردازنده</div>
            </div>
            <div>
              <div className="text-lg font-bold tabular-nums">
                {humanUptime(panel.uptime_seconds)}
              </div>
              <div className="text-xs text-content-subtle">آپ‌تایم</div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
