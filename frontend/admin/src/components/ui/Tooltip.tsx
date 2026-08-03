import { clsx } from "clsx";
import type { ReactNode } from "react";

/**
 * Lightweight CSS-only tooltip (hover + keyboard focus, no positioning library).
 *
 * The trigger keeps `tabIndex={0}` so the tip is reachable without a pointer, and the label is also
 * exposed via `aria-label`, so a screen reader gets it even though the bubble itself is decorative.
 */
export function Tooltip({
  label,
  children,
  side = "top",
  className,
}: {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom";
  className?: string;
}) {
  return (
    <span className={clsx("group/tip relative inline-flex", className)}>
      <span tabIndex={0} aria-label={label} className="inline-flex rounded outline-none">
        {children}
      </span>
      <span
        role="tooltip"
        className={clsx(
          "pointer-events-none absolute start-1/2 z-40 w-max max-w-[16rem] -translate-x-1/2 rounded-lg",
          "bg-content px-2 py-1 text-xs font-medium text-surface opacity-0 shadow-raised transition-opacity",
          "group-hover/tip:opacity-100 group-focus-within/tip:opacity-100",
          side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5",
        )}
      >
        {label}
      </span>
    </span>
  );
}
