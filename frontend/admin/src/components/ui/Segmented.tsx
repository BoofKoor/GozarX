import { clsx } from "clsx";
import type { ReactNode } from "react";

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
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={clsx(
        "inline-flex items-center gap-0.5 rounded-xl border border-line bg-surface-sunken p-0.5",
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            role="radio"
            aria-checked={active}
            title={opt.title}
            onClick={() => onChange(opt.value)}
            className={clsx(
              "rounded-[10px] font-medium transition",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
              active
                ? "bg-surface text-content shadow-card"
                : "text-content-muted hover:text-content",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
