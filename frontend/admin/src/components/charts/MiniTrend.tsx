import { useId } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { seriesColor } from "@/lib/chartTheme";

import { smoothPath, type Point } from "./geometry";

const W = 260;
const H = 54;

/**
 * A thumbnail series, for a record dialog.
 *
 * Deliberately not `HeroSparkline` at a smaller size. That one is width-driven with a fixed aspect,
 * so at a dialog's width it draws a 340px-tall chart; and it carries a marker, a delta pill and day
 * labels, none of which a thumbnail wants. `preserveAspectRatio="none"` is safe HERE and nowhere
 * else in the panel: there is no text and no round marker inside to distort — only a stroke, whose
 * weight the squeeze changes by a fraction of a pixel.
 *
 * It fades in at the axis for the same reason every other window in the panel does: thirty days is
 * a slice of a longer history, and a line that starts hard on the edge claims the user's first
 * claim happened there.
 */
export function MiniTrend({ values, ariaLabel }: { values: number[]; ariaLabel: string }) {
  useIsDark(); // re-render on a theme flip so the token colours re-resolve
  const uid = useId().replace(/:/g, "");
  if (values.length < 2) return null;

  const color = seriesColor(0);
  const max = Math.max(...values, 1);
  const x = (i: number) => (i / (values.length - 1)) * W;
  const y = (v: number) => 3 + (1 - v / max) * (H - 8);
  const pts: Point[] = values.map((v, i) => [x(i), y(v)]);
  const line = smoothPath(pts);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={ariaLabel}
      className="block h-[54px] w-full"
    >
      <defs>
        <linearGradient
          id={`${uid}-fill`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="0"
          y2={H}
        >
          <stop offset="0%" stopColor={color} stopOpacity=".34" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
        <linearGradient
          id={`${uid}-head`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2={W * 0.3}
          y2="0"
        >
          <stop offset="0%" stopColor="#000" />
          <stop offset="100%" stopColor="#fff" />
        </linearGradient>
        <mask id={`${uid}-mask`}>
          <rect width={W} height={H} fill={`url(#${uid}-head)`} />
        </mask>
      </defs>
      <g mask={`url(#${uid}-mask)`}>
        <path d={`${line}L${W},${H}L0,${H}Z`} fill={`url(#${uid}-fill)`} />
        <path
          d={line}
          fill="none"
          stroke={color}
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </svg>
  );
}
