import { clsx } from "clsx";
import { type KeyboardEvent, useRef } from "react";

import { useI18n } from "@/i18n";
import { localizeDigits } from "@/lib/format";

/**
 * Claims per hour of day, as 24 bars.
 *
 * The same data the dashboard derives its peak hour from, put where a timing decision is actually
 * made — scheduling blind is how a broadcast lands at 04:00.
 *
 * With `onPick` the strip is a real control: a radio group of 24 hours. Each hour is the FULL
 * column, not its bar — the bar itself was the button, so a quiet hour was a 2px-tall target — and
 * the group is ONE tab stop with the arrows walking it, where it used to be 24 stops between the
 * composer and its Send button. Without `onPick` it is a read-only chart, out of the tab order.
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
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  // The one hour in the tab order: the chosen one, or the first when none is.
  const current = mark != null && mark >= 0 && mark < counts.length ? mark : 0;

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (!onPick) return;
    // PHYSICAL arrows: the strip is a clock laid out left to right in both languages, so right is
    // later whatever the page's reading direction.
    const next =
      e.key === "ArrowRight" || e.key === "ArrowUp"
        ? Math.min(counts.length - 1, current + 1)
        : e.key === "ArrowLeft" || e.key === "ArrowDown"
          ? Math.max(0, current - 1)
          : e.key === "Home"
            ? 0
            : e.key === "End"
              ? counts.length - 1
              : null;
    if (next == null) return;
    e.preventDefault();
    onPick(next);
    buttons.current[next]?.focus();
  }

  return (
    <div className={className}>
      {/* Hours run left-to-right in both languages: a clock is not a sentence. */}
      <div
        className="flex h-11 items-stretch gap-[2px]"
        dir="ltr"
        aria-hidden={!onPick}
        role={onPick ? "radiogroup" : undefined}
        aria-label={onPick ? t("hours.aria") : undefined}
        onKeyDown={onKeyDown}
      >
        {counts.map((v, h) => {
          const bar = (
            <span
              aria-hidden
              style={{ height: `${Math.max(4, (v / max) * 100)}%` }}
              className={clsx(
                "mt-auto block min-h-[2px] w-full rounded-t-sm transition",
                h === mark ? "bg-brand" : "bg-brand/20",
                onPick && "group-hover:bg-brand/60",
              )}
            />
          );
          return onPick ? (
            <button
              key={h}
              ref={(el) => {
                buttons.current[h] = el;
              }}
              type="button"
              role="radio"
              aria-checked={h === mark}
              tabIndex={h === current ? 0 : -1}
              onClick={() => onPick(h)}
              // A column is a few pixels wide, so it has to SAY which hour it is rather than leave
              // that to its position.
              aria-label={t("hours.pick", { h: hourLabel(h) })}
              className="group flex flex-1 cursor-pointer flex-col rounded-t-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              {bar}
            </button>
          ) : (
            <span key={h} className="flex flex-1 flex-col">
              {bar}
            </span>
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
