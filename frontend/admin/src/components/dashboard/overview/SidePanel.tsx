import { clsx } from "clsx";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { tokenColor } from "@/lib/chartTheme";
import { formatNumber } from "@/lib/format";

/**
 * A section heading inside the side panel.
 *
 * Sized off the design, not off Tailwind's ladder: 0.95rem in a 23px box. As `text-sm` with `pt-2
 * pb-1` it was 14px in a 32px box — a full third taller, three times over, in the one column where
 * height is scarcest.
 */
export function SideHead({ children }: { children: ReactNode }) {
  return (
    <div className="mt-0.5 flex items-center gap-2 text-[0.95rem] font-bold text-content">
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
 *
 * The three type sizes here are the design's (1.4rem / 0.8rem / 0.585rem), and the spread between
 * them is the point. Built from Tailwind's ladder instead — `text-lg` value over a `text-sm` label —
 * the figure was 18px against a 14px label, and the panel measured 45% of its text runs at ONE size
 * where the design uses nine. Compressed from both ends, the number stops being the thing you read.
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
    <div className="flex items-center gap-3 rounded-[13px] bg-surface-raised px-[0.9rem] py-[0.8rem]">
      {/* Wraps rather than truncates — which is what the design's 1.4 line-height on this label is
          for. Clipped instead, the English "Online users" lost its second word to a caption beside
          it that was merely longer, and a label is not the thing that should give way. */}
      <div className="min-w-0 flex-1 text-[0.8rem] leading-[1.4] text-content-muted">{label}</div>
      <div className="relative grid h-[3.05rem] w-[3.05rem] shrink-0 place-items-center">
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
        <Icon className="relative h-[1.05rem] w-[1.05rem] text-brand" />
      </div>
      <div className="shrink-0 text-end">
        <div className="text-[0.585rem] uppercase tracking-[0.085em] text-content-subtle">
          {outOfLabel} {formatNumber(outOf)}
        </div>
        <div className="text-[1.4rem] font-bold leading-tight tracking-[-0.02em] tabular-nums text-content">
          {formatNumber(value)}
        </div>
      </div>
    </div>
  );
}

/**
 * One line of the service-health list: a state dot, what it is, and its current reading.
 *
 * The dot carries a soft halo of its own colour, which is what makes a 8px mark read as a STATUS
 * light rather than a bullet. The reading is weight 500, not 600 — it sits beside a muted label, so
 * it only has to be the heavier of the two.
 */
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
  const DOT = {
    ok: "bg-success-500 ring-success-500/20",
    warn: "bg-warning-500 ring-warning-500/20",
    bad: "bg-danger-500 ring-danger-500/20",
  };
  return (
    <div
      className={clsx(
        "flex items-center gap-[0.55rem] py-[0.62rem] text-[0.78rem]",
        !last && "border-b border-line",
      )}
    >
      <span className={clsx("h-2 w-2 shrink-0 rounded-full ring-[3px]", DOT[tone])} aria-hidden />
      <span className="min-w-0 flex-1 truncate text-content-muted">{label}</span>
      {/* The reading is often a Latin unit next to a Persian sentence, so it is isolated. */}
      <b className="shrink-0 font-medium text-content" style={{ unicodeBidi: "isolate" }}>
        {value}
      </b>
    </div>
  );
}
