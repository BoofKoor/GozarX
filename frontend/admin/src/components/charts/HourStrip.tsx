import { clsx } from "clsx";

import { useI18n } from "@/i18n";
import { localizeDigits } from "@/lib/format";

/**
 * Claims per hour of day, as 24 bars.
 *
 * The same data the dashboard derives its peak hour from, put where a timing decision is actually
 * made — scheduling blind is how a broadcast lands at 04:00.
 *
 * With `onPick` each bar becomes a real control, so the hour can be chosen by keyboard as well as
 * by mouse; without it the strip is a read-only chart and stays out of the tab order entirely.
 * `mark` highlights one hour — the peak, or the hour a message would land in.
 */
export function HourStrip({
  counts,
  mark,
  onPick,
  className,
}: {
  /** 24 values, index = hour in the reporting timezone. */
  counts: number[];
  mark?: number;
  /** Makes the strip interactive: picks the hour a scheduled broadcast should go out. */
  onPick?: (hour: number) => void;
  className?: string;
}) {
  const { t } = useI18n();
  const max = Math.max(1, ...counts);
  const hourLabel = (h: number) => localizeDigits(`${String(h).padStart(2, "0")}:00`);

  return (
    <div className={className}>
      {/* Hours run left-to-right in both languages: a clock is not a sentence. */}
      <div className="flex h-11 items-end gap-[2px]" dir="ltr" aria-hidden={!onPick}>
        {counts.map((v, h) => {
          const bar = clsx(
            "min-h-[2px] flex-1 rounded-t-sm transition",
            h === mark ? "bg-brand" : "bg-brand/20",
          );
          const style = { height: `${Math.max(4, (v / max) * 100)}%` };
          return onPick ? (
            <button
              key={h}
              type="button"
              onClick={() => onPick(h)}
              // A bar is a couple of pixels wide, so it has to SAY which hour it is rather than
              // leave that to its position.
              aria-label={t("hours.pick", { h: hourLabel(h) })}
              aria-pressed={h === mark}
              style={style}
              className={clsx(bar, "cursor-pointer hover:bg-brand/60")}
            />
          ) : (
            <span key={h} style={style} className={bar} />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-content-subtle" dir="ltr">
        {[0, 6, 12, 18, 23].map((h) => (
          <span key={h}>{localizeDigits(String(h).padStart(2, "0"))}</span>
        ))}
      </div>
    </div>
  );
}
