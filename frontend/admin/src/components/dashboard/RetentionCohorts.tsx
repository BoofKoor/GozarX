import { clsx } from "clsx";
import { CalendarRange } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { faPct, formatNumber, shortDay } from "@/lib/format";
import type { Retention } from "@/types/api";

/** Colour ramp for a retention cell: transparent at 0%, solid brand at 100%. Alpha is bucketed so
 *  neighbouring cells stay visually distinct instead of blending into a gradient. */
function cellClass(pct: number): string {
  if (pct <= 0) return "bg-surface-sunken text-content-subtle";
  if (pct < 20) return "bg-brand/15 text-content";
  if (pct < 40) return "bg-brand/30 text-content";
  if (pct < 60) return "bg-brand/50 text-white";
  if (pct < 80) return "bg-brand/70 text-white";
  return "bg-brand text-white";
}

/**
 * Weekly signup cohorts × weeks-since-signup. Column 0 is the signup week (activation); later
 * columns are the share that came back. This is the only view that answers "do people stick?" —
 * every other panel on the dashboard measures a single moment.
 */
export function RetentionCohorts({ data }: { data: Retention }) {
  const width = Math.max(1, ...data.cohorts.map((c) => c.retention.length));
  // Average activation across cohorts big enough to mean something.
  const sized = data.cohorts.filter((c) => c.size > 0);
  const avgActivation = sized.length
    ? sized.reduce((s, c) => s + (c.retention[0] ?? 0), 0) / sized.length
    : 0;

  return (
    <Card>
      <CardHeader
        title="نگه‌داشت هفتگی (کوهورت)"
        sub="هر سطر یک هفتهٔ ثبت‌نام؛ ستون‌ها درصد همان گروه که در هفته‌های بعد کانفیگ گرفته‌اند."
        icon={CalendarRange}
        action={
          sized.length > 0 ? (
            <Badge tone="brand">میانگین فعال‌سازی {faPct(avgActivation)}</Badge>
          ) : undefined
        }
      />
      {data.cohorts.length === 0 ? (
        <EmptyState title="هنوز کوهورتی نیست" message="پس از چند هفته فعالیت اینجا پر می‌شود." />
      ) : (
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-xs">
            <thead>
              <tr>
                <th className="p-1.5 text-start font-semibold text-content-muted">هفتهٔ ثبت‌نام</th>
                <th className="p-1.5 text-start font-semibold text-content-muted">اندازه</th>
                {Array.from({ length: width }).map((_, i) => (
                  <th key={i} className="p-1.5 text-center font-semibold text-content-muted">
                    {i === 0 ? "همان هفته" : `هفتهٔ ${formatNumber(i)}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.cohorts.map((c) => (
                <tr key={c.week}>
                  <td className="whitespace-nowrap p-1.5 text-content-muted">{shortDay(c.week)}</td>
                  <td className="p-1.5 tabular-nums text-content">{formatNumber(c.size)}</td>
                  {Array.from({ length: width }).map((_, i) => {
                    const pct = c.retention[i];
                    // A cohort younger than `i` weeks has no cell here — leave it blank rather than
                    // painting a 0%, which would read as "nobody came back".
                    if (pct === undefined) {
                      return <td key={i} className="p-0.5" />;
                    }
                    return (
                      <td key={i} className="p-0.5">
                        <div
                          className={clsx(
                            "rounded-md py-1.5 text-center tabular-nums",
                            cellClass(pct),
                          )}
                          title={`${faPct(pct)} از ${formatNumber(c.size)} نفر`}
                        >
                          {faPct(pct)}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
