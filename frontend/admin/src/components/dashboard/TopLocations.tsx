import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { NamedCount } from "@/types/api";
import { useI18n } from "@/i18n";

/** Div-based horizontal bar list (RTL-friendly, no recharts axis quirks). */
export function TopLocations({ data }: { data: NamedCount[] }) {
  const { t } = useI18n();
  const max = Math.max(1, ...data.map((d) => d.count));

  return (
    <Card>
      <CardHeader title={t("d.topLocations")} />
      {data.length === 0 ? (
        <div className="flex h-40 items-center justify-center text-sm text-content-subtle">
          {t("d.topLocations.empty")}
        </div>
      ) : (
        <ul className="space-y-3">
          {data.map((d) => (
            <li key={d.label}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="truncate text-content">{d.label}</span>
                <span className="font-medium tabular-nums text-content-muted">
                  {formatNumber(d.count)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
                <div
                  className="h-full rounded-full bg-brand transition-all"
                  style={{ width: `${(d.count / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
