import { clsx } from "clsx";

import { localizeDigits } from "@/lib/format";

/**
 * Claims per hour of day, as 24 bars.
 *
 * The same data the dashboard derives its peak hour from, put where a timing decision is actually
 * made. `mark` highlights one hour — the peak, or the hour a message would land in.
 */
export function HourStrip({
  counts,
  mark,
  className,
}: {
  /** 24 values, index = hour in the reporting timezone. */
  counts: number[];
  mark?: number;
  className?: string;
}) {
  const max = Math.max(1, ...counts);
  return (
    <div className={className}>
      {/* Hours run left-to-right in both languages: a clock is not a sentence. */}
      <div className="flex h-11 items-end gap-[2px]" dir="ltr" aria-hidden>
        {counts.map((v, h) => (
          <span
            key={h}
            style={{ height: `${Math.max(4, (v / max) * 100)}%` }}
            className={clsx(
              "min-h-[2px] flex-1 rounded-t-sm",
              h === mark ? "bg-brand" : "bg-brand/20",
            )}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-content-subtle" dir="ltr">
        {[0, 6, 12, 18, 23].map((h) => (
          <span key={h}>{localizeDigits(String(h).padStart(2, "0"))}</span>
        ))}
      </div>
    </div>
  );
}
