import { clsx } from "clsx";

import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber, localizeDigits } from "@/lib/format";
import type { HeatCell } from "@/types/api";
import { useI18n } from "@/i18n";

// Postgres dow: 0=Sunday .. 6=Saturday. Persian names indexed by that dow value.
const DOW_KEYS = [
  "d.dow.0",
  "d.dow.1",
  "d.dow.2",
  "d.dow.3",
  "d.dow.4",
  "d.dow.5",
  "d.dow.6",
] as const;
// The Persian week starts on Saturday, so render rows in that order.
const ROW_ORDER = [6, 0, 1, 2, 3, 4, 5];
const HOURS = Array.from({ length: 24 }, (_, h) => h);

function cellClass(count: number, max: number): string {
  if (count === 0) return "bg-surface-sunken";
  const t = count / max;
  if (t > 0.75) return "bg-brand";
  if (t > 0.5) return "bg-brand/70";
  if (t > 0.25) return "bg-brand/45";
  return "bg-brand/20";
}

/**
 * GitHub-style activity heatmap by weekday × hour (Asia/Tehran). Shows WHEN the bot is busy — the
 * peak hours to schedule broadcasts or expect load.
 *
 * Parameterised because "when do people CLAIM" and "when do people ARRIVE" are different questions
 * and only the first one was ever charted; both now render through this one component.
 */
export function ActivityHeatmap({
  cells,
  title,
  unit,
  axisNote,
}: {
  cells: HeatCell[];
  title?: string;
  unit?: string;
  axisNote?: string;
}) {
  const { t } = useI18n();
  const DOW_LABEL = DOW_KEYS.map((k) => t(k));
  const counts = new Map<string, number>();
  for (const c of cells) counts.set(`${c.dow}-${c.hour}`, c.count);
  const max = Math.max(1, ...cells.map((c) => c.count));
  const total = cells.reduce((s, c) => s + c.count, 0);

  return (
    <Card>
      <CardHeader
        title={title ?? t("d.heat.claims")}
        action={<span className="text-xs text-content-subtle">{axisNote ?? t("d.heat.axis")}</span>}
      />
      {total === 0 ? (
        <div className="flex h-40 items-center justify-center text-sm text-content-subtle">
          {t("d.heat.empty")}
        </div>
      ) : (
        <div className="overflow-x-auto" dir="ltr">
          <div className="min-w-[560px]">
            {/* hour axis (every 3h) */}
            <div className="mb-1 flex pl-14 text-[10px] text-content-subtle">
              {HOURS.map((h) => (
                <div key={h} className="flex-1 text-center">
                  {h % 3 === 0 ? localizeDigits(String(h)) : ""}
                </div>
              ))}
            </div>
            {ROW_ORDER.map((dow) => (
              <div key={dow} className="mb-1 flex items-center">
                <div className="w-14 shrink-0 pr-2 text-right text-[11px] text-content-muted">
                  {DOW_LABEL[dow]}
                </div>
                <div className="flex flex-1 gap-1">
                  {HOURS.map((h) => {
                    const c = counts.get(`${dow}-${h}`) ?? 0;
                    return (
                      <div
                        key={h}
                        title={`${DOW_LABEL[dow]} ${localizeDigits(String(h))}:${localizeDigits("00")} — ${formatNumber(c)} ${unit ?? t("d.heat.claimsUnit")}`}
                        className={clsx("aspect-square flex-1 rounded-[3px]", cellClass(c, max))}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
            {/* legend */}
            <div className="mt-2 flex items-center justify-end gap-1.5 pr-1 text-[10px] text-content-subtle">
              <span>{t("d.heat.low")}</span>
              {["bg-surface-sunken", "bg-brand/20", "bg-brand/45", "bg-brand/70", "bg-brand"].map(
                (c) => (
                  <span key={c} className={clsx("h-3 w-3 rounded-[3px]", c)} />
                ),
              )}
              <span>{t("d.heat.high")}</span>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
