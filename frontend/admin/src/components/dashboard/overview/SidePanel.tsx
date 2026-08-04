import { clsx } from "clsx";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { tokenColor } from "@/lib/chartTheme";
import { formatNumber } from "@/lib/format";

/** A section heading inside the side panel. */
export function SideHead({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 px-1 pb-1 pt-2 text-sm font-bold text-content">
      <span className="flex-1">{children}</span>
      <span className="text-content-subtle" aria-hidden>
        ⋮
      </span>
    </div>
  );
}

/**
 * A live figure with a progress ring and its own icon.
 *
 * The ring needs a denominator that MEANS something. There is no recorded all-time peak to compare
 * against, so `outOf` is a real, nameable population (this week's actives, say) and `outOfLabel`
 * says which — a gauge against an invented maximum is decoration.
 */
export function GaugeCard({
  icon: Icon,
  label,
  value,
  outOf,
  outOfLabel,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  outOf: number;
  outOfLabel: string;
}) {
  useIsDark(); // re-render on a theme flip so the ring colours re-resolve
  const r = 21;
  const c = 2 * Math.PI * r;
  const frac = outOf > 0 ? Math.min(1, value / outOf) : 0;
  return (
    <div className="flex items-center gap-3 rounded-xl bg-surface-sunken p-3">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-content-muted">{label}</div>
      </div>
      <div className="relative grid h-[50px] w-[50px] shrink-0 place-items-center">
        <svg viewBox="0 0 50 50" className="absolute inset-0 h-full w-full -rotate-90" aria-hidden>
          <circle cx="25" cy="25" r={r} fill="none" stroke={tokenColor("line")} strokeWidth="4" />
          <circle
            cx="25"
            cy="25"
            r={r}
            fill="none"
            stroke={tokenColor("brand-500")}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={`${(c * frac).toFixed(2)} ${c.toFixed(2)}`}
          />
        </svg>
        <Icon className="relative h-4 w-4 text-brand" />
      </div>
      <div className="shrink-0 text-end">
        <div className="text-[10px] text-content-subtle">
          {outOfLabel} {formatNumber(outOf)}
        </div>
        <div className="text-lg font-bold leading-tight tabular-nums text-content">
          {formatNumber(value)}
        </div>
      </div>
    </div>
  );
}

/** One line of the service-health list: a state dot, what it is, and its current reading. */
export function HealthRow({
  label,
  value,
  tone,
  last = false,
}: {
  label: string;
  value: ReactNode;
  tone: "ok" | "warn" | "bad";
  last?: boolean;
}) {
  const DOT = { ok: "bg-success-500", warn: "bg-warning-500", bad: "bg-danger-500" };
  return (
    <div className={clsx("flex items-center gap-2.5 py-2.5", !last && "border-b border-line")}>
      <span className={clsx("h-2 w-2 shrink-0 rounded-full", DOT[tone])} aria-hidden />
      <span className="min-w-0 flex-1 truncate text-sm text-content-muted">{label}</span>
      {/* The reading is often a Latin unit next to a Persian sentence, so it is isolated. */}
      <b className="shrink-0 text-sm font-semibold text-content" style={{ unicodeBidi: "isolate" }}>
        {value}
      </b>
    </div>
  );
}
