import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { NamedCount } from "@/types/api";

/** Div-based horizontal bar list (RTL-friendly, no recharts axis quirks). */
export function TopLocations({ data }: { data: NamedCount[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));

  return (
    <Card>
      <CardHeader title="پرطرفدارترین لوکیشن‌ها" />
      {data.length === 0 ? (
        <div className="flex h-40 items-center justify-center text-sm text-slate-400">
          هنوز کانفیگی دریافت نشده
        </div>
      ) : (
        <ul className="space-y-3">
          {data.map((d) => (
            <li key={d.label}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="truncate text-slate-700 dark:text-slate-200">{d.label}</span>
                <span className="font-medium tabular-nums text-slate-500">
                  {formatNumber(d.count)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
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
