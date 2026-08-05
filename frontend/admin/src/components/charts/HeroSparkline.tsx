import { useId } from "react";

import { useIsDark } from "@/hooks/useIsDark";

import { smoothPath, type Point } from "./geometry";

export interface HeroSparklineProps {
  /** One value per day, oldest first. */
  values: number[];
  /** Short day labels, same length as `values`. */
  labels: string[];
  /** Index of the day to mark with a band and a dot. */
  highlight: number;
  /** Already-formatted change for the pill above the marker, e.g. "+۱۴٪". Omitted renders none. */
  delta?: string;
  ariaLabel: string;
  className?: string;
}

const W = 268;
const H = 138;
const TOP = 30;
const PLOT_H = 66;
const PAD_X = 18;

/**
 * The trend inside the dashboard's hero tile, drawn on the brand fill.
 *
 * Two rules from the design decide everything here:
 *
 * 1. The LINE fades at both ends, because a seven-day window is a slice of a longer series and a
 *    line that starts hard on the edge claims the data began there. The fade gradient is anchored
 *    to the line's own extent, not to the viewBox — spanning the full width would put both ramps
 *    inside the side padding, where there is no line to fade, and the curve would appear at half
 *    opacity and pop.
 * 2. The BAND under the highlighted day does not fade. It is a marker, not part of the series, and
 *    dimming it weakens the one thing it exists to do. It runs straight down from the marker: an
 *    earlier version clipped it to the area under the curve, which tapered it into a teardrop
 *    whenever the marked day fell at either end of the window.
 */
export function HeroSparkline({
  values,
  labels,
  highlight,
  delta,
  ariaLabel,
  className,
}: HeroSparklineProps) {
  useIsDark(); // re-render on a theme flip so the fill under the curve re-resolves
  const uid = useId().replace(/:/g, "");

  if (values.length < 2) return null;

  const max = Math.max(...values);
  const min = Math.min(...values);
  const x = (i: number) => PAD_X + (i / (values.length - 1)) * (W - PAD_X * 2);
  const y = (v: number) => TOP + (1 - (v - min) / (max - min || 1)) * PLOT_H;

  const pts: Point[] = values.map((v, i) => [x(i), y(v)]);
  const line = smoothPath(pts);
  const hi = Math.max(0, Math.min(values.length - 1, highlight));
  const hx = x(hi);
  const hy = y(values[hi]);
  // The pill is measured from the string rather than laid out, so it can be centred and clamped
  // inside the frame — an SVG has no text metrics to ask.
  const pillW = delta ? Math.max(34, delta.length * 7.2 + 14) : 0;
  const pillX = Math.min(Math.max(hx - pillW / 2, 4), W - pillW - 4);
  const pillY = Math.max(hy - 30, 2);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} className={className}>
      <defs>
        <linearGradient
          id={`${uid}-ends`}
          gradientUnits="userSpaceOnUse"
          x1={x(0)}
          y1="0"
          x2={x(values.length - 1)}
          y2="0"
        >
          <stop offset="0%" stopColor="#000" />
          <stop offset="22%" stopColor="#fff" />
          <stop offset="78%" stopColor="#fff" />
          <stop offset="100%" stopColor="#000" />
        </linearGradient>
        <mask id={`${uid}-mask`}>
          <rect x="0" y="0" width={W} height={H} fill={`url(#${uid}-ends)`} />
        </mask>
      </defs>

      {/* A straight bar from the marker down, NOT a shape clipped to the curve: clipped, it
          tapered into a teardrop whenever the marked day sat at either end of the window. */}
      <rect
        x={hx - 13}
        y={hy}
        width="26"
        height={Math.max(0, H - 26 - hy)}
        rx="13"
        fill="#fff"
        opacity=".26"
      />

      <path
        d={line}
        fill="none"
        stroke="#fff"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        mask={`url(#${uid}-mask)`}
      />

      <circle cx={hx} cy={hy} r="4.5" className="fill-brand-600" stroke="#fff" strokeWidth="2.25" />

      {delta && (
        <g>
          <rect x={pillX} y={pillY} width={pillW} height="19" rx="9.5" fill="#fff" />
          {/* An SVG <text> obeys the document's direction, so a signed percentage rendered
              «۱۲٫۴٪+» with the sign trailing the number it belongs to. */}
          <text
            x={pillX + pillW / 2}
            y={pillY + 13.5}
            textAnchor="middle"
            fontSize="10.5"
            fontWeight="700"
            style={{ direction: "ltr" }}
            className="fill-brand-600"
          >
            {delta}
          </text>
        </g>
      )}

      {labels.map((label, i) => (
        <text
          key={i}
          x={x(i).toFixed(1)}
          y={H - 8}
          textAnchor="middle"
          fontSize="8.5"
          letterSpacing="0.9"
          fill="#fff"
          opacity={i === hi ? 1 : 0.55}
          fontWeight={i === hi ? 700 : 400}
        >
          {label}
        </text>
      ))}
    </svg>
  );
}
