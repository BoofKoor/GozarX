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
  className,
  children,
}: {
  value: ReactNode;
  label: string;
  delta?: ReactNode;
  hero?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className={clsx(
        "flex min-w-0 flex-col rounded-card p-4",
        className,
        // The hero tile is a GRADIENT, and its bottom padding is halved so the sparkline can bleed
        // to the tile's own edges (the design runs the curve and the marker column right out to
        // them; inset inside the padding it reads as a small chart parked in a big empty tile).
        hero ? "bg-hero pb-2 text-white shadow-hero" : "min-h-[139px] bg-surface shadow-card",
      )}
    >
      <div
        className={clsx(
          "text-[2rem] font-bold leading-[1.1] tracking-[-0.025em] tabular-nums",
          !hero && "text-content",
        )}
      >
        {value}
      </div>
      {/* An eyebrow, not body text: small, tracked out and quiet, so the figure above it is the only
          thing with weight in the tile. At `text-xs text-content-muted` the label competed with its
          own number and the four tiles read as four paragraphs. */}
      <div
        className={clsx(
          "mt-1.5 text-[10px] uppercase leading-[1.5] tracking-[0.085em]",
          hero ? "text-white/70" : "text-content-subtle",
        )}
      >
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
 * A "top X" card: a coloured glyph, what it is, and the FIGURE with its unit.
 *
 * The figure is the card. It is the biggest thing in it, and the name above it is a caption — the
 * card answers "how many claims did the top location get", and «۱٬۸۸۳» is the answer while
 * «Germany» is the question restated. Built the other way round, with the name bold at body size
 * and the count at 11px underneath, the row of four read as four labels and the numbers vanished.
 *
 * The glyph leads the line, on the reading-START edge, and the overflow dots close it. Each card
 * takes a different accent: four identical grey glyphs carry no information and read as unfinished.
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
    <div className="flex min-w-0 flex-col rounded-card bg-surface px-[14px] pb-4 pt-[15px] shadow-card">
      <div className="flex min-h-[41px] items-start gap-1.5">
        <span
          className={clsx(
            "grid h-[26px] w-[26px] shrink-0 place-items-center rounded-lg",
            TONE[tone],
          )}
        >
          <Icon className="h-[15px] w-[15px]" />
        </span>
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[0.085em] text-content-subtle">
            {label}
          </div>
          <div
            className={clsx(
              "truncate text-sm font-bold text-content",
              mono && "font-mono text-[12px] tracking-[-0.01em]",
            )}
            style={mono ? { unicodeBidi: "isolate" } : undefined}
            dir={mono ? "ltr" : undefined}
          >
            {headline}
          </div>
        </div>
        <span
          className="ms-auto ps-1 text-base leading-none tracking-[0.1em] text-content-subtle"
          aria-hidden
        >
          ⋮
        </span>
      </div>
      <div className="mt-auto flex items-baseline pt-3.5 text-[22px] font-bold tracking-[-0.02em] tabular-nums text-content">
        <span>{value}</span>
        {/* A rule, not a gap: the unit belongs to the number but is not part of it. */}
        <small className="ms-2 border-s border-line ps-[7px] text-[11px] font-normal text-content-subtle">
          {unit}
        </small>
      </div>
    </div>
  );
}
