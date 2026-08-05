import type { ReactNode } from "react";

import { t } from "@/i18n";
import type { ChartTheme } from "@/lib/chartTheme";
import { localizeDigits } from "@/lib/format";

/**
 * Shared recharts building blocks so every chart in the panel has the same axes, grid, tooltip and
 * empty state. Recharts inspects its children by component type, so axes can't be wrapped in custom
 * components — these are prop factories instead, spread onto the real recharts elements.
 */

export function axisProps(t: ChartTheme) {
  return {
    tick: { fontSize: 11, fill: t.axis },
    tickLine: false,
    axisLine: false,
    // Recharts prints raw numbers, so every value axis in the panel read "300 / 225 / 150" in
    // Latin digits while the rest of the page — including the axis right below it — was Persian.
    // A no-op in English, and on a tick that is already a formatted string.
    tickFormatter: (v: unknown) => localizeDigits(String(v)),
  } as const;
}

export function gridProps(t: ChartTheme) {
  return { strokeDasharray: "3 3", vertical: false, stroke: t.grid } as const;
}

/** A top-to-transparent fill for area charts. Render inside recharts' `<defs>`. */
export function AreaGradient({ id, color }: { id: string; color: string }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={0.32} />
      <stop offset="100%" stopColor={color} stopOpacity={0} />
    </linearGradient>
  );
}

/**
 * Fixed-height chart area. `dir="ltr"` because a time axis reads left-to-right (oldest → newest)
 * even inside this RTL panel — flipping it would put "today" on the left and read as going backwards.
 */
export function ChartFrame({
  height = "h-64",
  empty,
  emptyLabel,
  children,
}: {
  height?: string;
  empty?: boolean;
  emptyLabel?: string;
  children: ReactNode;
}) {
  return (
    <div className={height} dir="ltr">
      {empty ? (
        <div
          className="flex h-full items-center justify-center text-sm text-content-subtle"
          dir="rtl"
        >
          {emptyLabel ?? t("d.heat.empty")}
        </div>
      ) : (
        children
      )}
    </div>
  );
}

/** Dot legend for charts whose series aren't self-evident. Sits above the plot, in RTL order. */
export function ChartLegend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-content-muted">
      {items.map((s) => (
        <span key={s.label} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: s.color }} aria-hidden />
          {s.label}
        </span>
      ))}
    </div>
  );
}
