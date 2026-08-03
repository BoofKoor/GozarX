import { clsx } from "clsx";

import { Card } from "@/components/ui/Card";
import type { HealthStatus, Probe, SystemHealth } from "@/types/api";

const STATUS_META: Record<HealthStatus, { label: string; ring: string; dot: string }> = {
  ok: { label: "سالم", ring: "bg-success-500/12", dot: "bg-success" },
  degraded: { label: "هشدار", ring: "bg-warning-500/12", dot: "bg-warning" },
  down: { label: "قطع", ring: "bg-danger-500/12", dot: "bg-danger" },
};

function ProbeChip({ label, probe }: { label: string; probe: Probe }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-line px-3 py-2">
      <span
        className={clsx("h-2.5 w-2.5 shrink-0 rounded-full", probe.ok ? "bg-success" : "bg-danger")}
      />
      <span className="text-sm text-content-muted">{label}</span>
      <span className="ms-auto text-xs tabular-nums text-content-subtle">
        {probe.ok
          ? probe.latency_ms != null
            ? `${probe.latency_ms}ms`
            : "ok"
          : (probe.detail ?? "down")}
      </span>
    </div>
  );
}

export function HealthBanner({ data }: { data: SystemHealth }) {
  const meta = STATUS_META[data.status];
  const when = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("fa-IR") : "";
  return (
    <Card padded={false}>
      <div className={clsx("flex items-center gap-3 rounded-t-2xl px-5 py-4", meta.ring)}>
        <span className="relative flex h-3 w-3">
          {data.status !== "down" && (
            <span
              className={clsx(
                "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
                meta.dot,
              )}
            />
          )}
          <span className={clsx("relative inline-flex h-3 w-3 rounded-full", meta.dot)} />
        </span>
        <div className="text-lg font-bold">وضعیت سرویس: {meta.label}</div>
        <div className="ms-auto text-xs text-content-muted">به‌روزرسانی: {when}</div>
      </div>
      <div className="grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
        <ProbeChip label="دیتابیس" probe={data.db} />
        <ProbeChip label="Redis" probe={data.redis} />
        <ProbeChip label="پنل" probe={data.panel} />
        <ProbeChip label="تلگرام" probe={data.telegram} />
      </div>
    </Card>
  );
}
