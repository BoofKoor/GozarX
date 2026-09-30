import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { NamedCount } from "@/types/api";
import { useI18n } from "@/i18n";

/** Div-based horizontal bar list (RTL-friendly, no recharts axis quirks).
 *
 *  `total` is how many distinct locations the window had. The list is capped at ten, and a capped
 *  list that does not say what it hid reads as the whole picture. */
export function TopLocations({ data, total }: { data: NamedCount[]; total?: number }) {
  const { t } = useI18n();
  const max = Math.max(1, ...data.map((d) => d.count));
  const hidden = total != null ? Math.max(0, total - data.length) : 0;

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
          {hidden > 0 && (
            <li className="text-xs text-content-subtle">
              {t("d.topLocations.more", { n: formatNumber(hidden) })}
            </li>
          )}
        </ul>
      )}
    </Card>
  );
}
