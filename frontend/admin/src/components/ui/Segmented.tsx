import { clsx } from "clsx";
import { type KeyboardEvent, type ReactNode, useRef } from "react";

export interface SegmentedOption<T extends string | number> {
  value: T;
  label: ReactNode;
  /** Optional accessible name when `label` is only a glyph/number. */
  title?: string;
}

/**
 * Segmented control — the panel's single pattern for a small, mutually exclusive choice (chart
 * range, list filter). Replaces the loose rows of hand-styled `<button>`s that each page repeated
 * with slightly different classes.
 *
 * `role="radiogroup"` is a promise, and this keeps it the way `Tabs` keeps `tablist`'s: ONE tab
 * stop (roving tabindex on the checked option), arrows that step and select — swapped in RTL, where
 * the next option is to the left — and Home/End. With only the roles, a screen reader said "radio,
 * 1 of 4" and the arrow key it then suggested did nothing.
 */
export function Segmented<T extends string | number>({
  value,
  onChange,
  options,
  size = "md",
  ariaLabel,
  className,
}: {
  value: T;
  onChange: (next: T) => void;
  options: SegmentedOption<T>[];
  size?: "sm" | "md";
  ariaLabel?: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const index = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    // The computed direction in a browser; the nearest `dir` where there is no layout (jsdom).
    const el = e.currentTarget;
    const rtl =
      (getComputedStyle(el).direction || el.closest("[dir]")?.getAttribute("dir")) === "rtl";
    const forward = rtl ? "ArrowLeft" : "ArrowRight";
    const back = rtl ? "ArrowRight" : "ArrowLeft";
    const n = options.length;
    const next =
      e.key === forward || e.key === "ArrowDown"
        ? (index + 1) % n
        : e.key === back || e.key === "ArrowUp"
          ? (index - 1 + n) % n
          : e.key === "Home"
            ? 0
            : e.key === "End"
              ? n - 1
              : null;
    if (next == null || n === 0) return;
    e.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={clsx(
        // No container: the design lets the options sit on the page and rings only the active
        // one. A bordered tray around all of them read as a second card competing with the chart.
        "inline-flex items-center gap-1",
        className,
      )}
    >
      {options.map((opt, i) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={i === index ? 0 : -1}
            title={opt.title}
            onClick={() => onChange(opt.value)}
            className={clsx(
              "rounded-[10px] font-medium transition",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
              "border",
              active
                ? "border-line-strong text-content"
                : "border-transparent text-content-muted hover:text-content",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
