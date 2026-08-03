import { clsx } from "clsx";
import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { useIsDark } from "@/hooks/useIsDark";
import { tokenColor } from "@/lib/chartTheme";
import { faPct } from "@/lib/format";

type Tone = "brand" | "success" | "info" | "warning" | "danger" | "neutral";

const TONE_CHIP: Record<Tone, string> = {
  brand: "bg-brand/12 text-brand",
  success: "bg-success-500/12 text-success-700",
  info: "bg-info-500/12 text-info-700",
  warning: "bg-warning-500/12 text-warning-700",
  danger: "bg-danger-500/12 text-danger-700",
  neutral: "bg-surface-sunken text-content-muted",
};

// Sparklines are inline SVG, so they need a real colour string rather than a class — resolved from
// the same tokens the chip classes use, which keeps them correct in both themes.
const TONE_TOKEN: Record<Tone, string> = {
  brand: "brand-500",
  success: "success-500",
  info: "info-500",
  warning: "warning-500",
  danger: "danger-500",
  neutral: "text-subtle",
};

/** A colored ▲/▼ delta chip. `goodWhenUp` decides which direction is green (default: up = good). */
function DeltaChip({ value, goodWhenUp = true }: { value: number; goodWhenUp?: boolean }) {
  if (!Number.isFinite(value) || value === 0) return null;
  const up = value > 0;
  const good = up === goodWhenUp;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
        good ? "bg-success-500/12 text-success-700" : "bg-danger-500/12 text-danger-700",
      )}
    >
      {up ? "▲" : "▼"} {faPct(Math.abs(value))}
    </span>
  );
}

/** A tiny inline-SVG sparkline (no chart library) for the KPI cards. */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;
  const w = 72;
  const h = 28;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`)
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="shrink-0"
      aria-hidden
    >
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "brand",
  hint,
  pulse,
  delta,
  deltaGoodWhenUp = true,
  spark,
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: Tone;
  hint?: string;
  /** Show a live "ping" dot on the icon — used for the online-now KPI. */
  pulse?: boolean;
  /** Percent change vs the prior period — rendered as a colored ▲/▼ chip. */
  delta?: number | null;
  /** Whether an increase is "good" (green). Default true; set false for e.g. churn. */
  deltaGoodWhenUp?: boolean;
  /** Optional mini sparkline series. */
  spark?: number[];
}) {
  useIsDark(); // the sparkline stroke resolves a CSS token — re-render when the theme flips
  return (
    <Card className="animate-fade-in flex items-center gap-4">
      <div
        className={clsx(
          "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl",
          TONE_CHIP[tone],
        )}
      >
        <Icon className="h-6 w-6" />
        {pulse && (
          <span className="absolute -left-0.5 -top-0.5 flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success-500 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-success-500" />
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className="text-2xl font-bold tabular-nums text-content">{value}</div>
          {delta != null && <DeltaChip value={delta} goodWhenUp={deltaGoodWhenUp} />}
        </div>
        <div className="truncate text-sm text-content-muted">{label}</div>
        {hint && <div className="mt-0.5 truncate text-xs text-content-subtle">{hint}</div>}
      </div>
      {spark && spark.length > 1 && (
        <div dir="ltr" className="hidden sm:block">
          <Sparkline data={spark} color={tokenColor(TONE_TOKEN[tone])} />
        </div>
      )}
    </Card>
  );
}
