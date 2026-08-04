import { clsx } from "clsx";

import { Card } from "@/components/ui/Card";
import { useI18n, type MessageKey } from "@/i18n";
import { faTime } from "@/lib/format";
import type { HealthStatus, Probe, SystemHealth } from "@/types/api";

const STATUS_META: Record<HealthStatus, { label: MessageKey; ring: string; dot: string }> = {
  ok: { label: "sys.status.ok", ring: "bg-success-500/15", dot: "bg-success" },
  degraded: { label: "sys.status.degraded", ring: "bg-warning-500/15", dot: "bg-warning" },
  down: { label: "sys.status.down", ring: "bg-danger-500/15", dot: "bg-danger" },
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
  const { t } = useI18n();
  const meta = STATUS_META[data.status];
  const when = data.generated_at ? faTime(data.generated_at) : "";
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
        <div className="text-lg font-bold">{t("sys.status", { label: t(meta.label) })}</div>
        <div className="ms-auto text-xs text-content-muted">{t("sys.updated", { when })}</div>
      </div>
      <div className="grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
        <ProbeChip label={t("sys.probe.db")} probe={data.db} />
        <ProbeChip label="Redis" probe={data.redis} />
        <ProbeChip label={t("sys.probe.panel")} probe={data.panel} />
        <ProbeChip label={t("sys.probe.telegram")} probe={data.telegram} />
      </div>
    </Card>
  );
}
