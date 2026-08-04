import { clsx } from "clsx";
import { ArrowDown, ArrowUp, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { faPct } from "@/lib/format";

/**
 * A delta chip.
 *
 * `goodWhenDown` exists because "time to first claim fell 12%" is an improvement while "signups
 * fell 12%" is not. The sign stays the arithmetic one; only the colour flips, so the number never
 * has to lie about its direction.
 */
export function Delta({
  pct,
  goodWhenDown = false,
  newLabel,
}: {
  pct: number | null | undefined;
  goodWhenDown?: boolean;
  newLabel: string;
}) {
  if (pct == null) {
    // No baseline is not "flat" — a first window with real activity would otherwise read as 0%.
    return <span className="text-xs font-medium text-content-subtle">{newLabel}</span>;
  }
  const rose = pct > 0;
  const good = goodWhenDown ? !rose : rose;
  const Icon = rose ? ArrowUp : ArrowDown;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 text-xs font-semibold",
        good ? "text-success-700" : "text-danger-700",
      )}
      style={{ unicodeBidi: "isolate" }}
    >
      <Icon className="h-3.5 w-3.5" />
      {faPct(Math.abs(pct))}
    </span>
  );
}

/** A KPI tile. `hero` is the brand-filled one that carries a sparkline instead of a delta. */
export function KpiTile({
  value,
  label,
  delta,
  hero = false,
  children,
}: {
  value: ReactNode;
  label: string;
  delta?: ReactNode;
  hero?: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      className={clsx(
        "flex min-w-0 flex-col rounded-2xl p-4",
        hero ? "bg-brand text-white shadow-glow" : "bg-surface shadow-card",
      )}
    >
      <div
        className={clsx(
          "text-[2rem] font-bold leading-tight tracking-tight tabular-nums",
          !hero && "text-content",
        )}
      >
        {value}
      </div>
      <div className={clsx("mt-1 text-xs", hero ? "text-white/75" : "text-content-muted")}>
        {label}
      </div>
      {/* The delta is pushed to the bottom so a two-line label never shoves it out of alignment
          with the tiles beside it. */}
      {delta && <div className="mt-auto pt-3">{delta}</div>}
      {children}
    </div>
  );
}

/**
 * A "top X" card: a coloured glyph, what it is, and the figure with its unit.
 *
 * Each card takes a different accent. Four identical grey glyphs carry no information and read as
 * unfinished; the colours are the same validated four the charts use.
 */
export function TopCard({
  icon: Icon,
  tone,
  label,
  headline,
  value,
  unit,
  mono = false,
}: {
  icon: LucideIcon;
  tone: 1 | 2 | 3 | 4;
  label: string;
  headline: ReactNode;
  value: ReactNode;
  unit: string;
  mono?: boolean;
}) {
  const TONE: Record<number, string> = {
    1: "bg-chart-1/20 text-chart-1",
    2: "bg-chart-3/20 text-chart-3",
    3: "bg-chart-2/20 text-chart-2",
    4: "bg-chart-4/20 text-chart-4",
  };
  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-2xl bg-surface p-4 shadow-card">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate text-[11px] text-content-subtle">{label}</div>
          <div
            className={clsx("mt-0.5 truncate font-bold text-content", mono && "font-mono text-sm")}
            style={mono ? { unicodeBidi: "isolate" } : undefined}
            dir={mono ? "ltr" : undefined}
          >
            {headline}
          </div>
        </div>
        <span className={clsx("grid h-8 w-8 shrink-0 place-items-center rounded-xl", TONE[tone])}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-bold tabular-nums text-content">{value}</span>
        <span className="text-[11px] text-content-subtle">{unit}</span>
      </div>
    </div>
  );
}
