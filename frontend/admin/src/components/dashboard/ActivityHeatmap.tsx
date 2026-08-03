import { clsx } from "clsx";

import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber, toFaDigits } from "@/lib/format";
import type { HeatCell } from "@/types/api";

// Postgres dow: 0=Sunday .. 6=Saturday. Persian names indexed by that dow value.
const DOW_LABEL = ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه"];
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
  title = "نقشهٔ حرارتی دریافت‌ها (به وقت تهران)",
  unit = "دریافت",
  axisNote = "بر حسب روز × ساعت",
}: {
  cells: HeatCell[];
  title?: string;
  unit?: string;
  axisNote?: string;
}) {
  const counts = new Map<string, number>();
  for (const c of cells) counts.set(`${c.dow}-${c.hour}`, c.count);
  const max = Math.max(1, ...cells.map((c) => c.count));
  const total = cells.reduce((s, c) => s + c.count, 0);

  return (
    <Card>
      <CardHeader
        title={title}
        action={<span className="text-xs text-content-subtle">{axisNote}</span>}
      />
      {total === 0 ? (
        <div className="flex h-40 items-center justify-center text-sm text-content-subtle">
          داده‌ای برای این بازه نیست
        </div>
      ) : (
        <div className="overflow-x-auto" dir="ltr">
          <div className="min-w-[560px]">
            {/* hour axis (every 3h) */}
            <div className="mb-1 flex pl-14 text-[10px] text-content-subtle">
              {HOURS.map((h) => (
                <div key={h} className="flex-1 text-center">
                  {h % 3 === 0 ? toFaDigits(String(h)) : ""}
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
                        title={`${DOW_LABEL[dow]} ${toFaDigits(String(h))}:۰۰ — ${formatNumber(c)} ${unit}`}
                        className={clsx("aspect-square flex-1 rounded-[3px]", cellClass(c, max))}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
            {/* legend */}
            <div className="mt-2 flex items-center justify-end gap-1.5 pr-1 text-[10px] text-content-subtle">
              <span>کم</span>
              {["bg-surface-sunken", "bg-brand/20", "bg-brand/45", "bg-brand/70", "bg-brand"].map(
                (c) => (
                  <span key={c} className={clsx("h-3 w-3 rounded-[3px]", c)} />
                ),
              )}
              <span>زیاد</span>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
