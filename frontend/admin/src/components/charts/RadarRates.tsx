import { useId } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { tokenColor } from "@/lib/chartTheme";
import { formatNumber } from "@/lib/format";
import { useI18n } from "@/i18n";

import { rosePath, rosePoints, spokeAngles } from "./geometry";

export interface RadarAxis {
  label: string;
  /** Percentage, 0–`max`. */
  value: number;
  /** Long form for the hover title. */
  title?: string;
}

export interface RadarRatesProps {
  axes: RadarAxis[];
  max?: number;
  className?: string;
}

const W = 340;
const H = 254;
const CX = W / 2;
const CY = 122;
const R = 92;
const STEPS = [0.25, 0.5, 0.75, 1];
/** Diagonal the scale numbers run down, clear of all four spokes. */
const TICK_ANGLE = (52 * Math.PI) / 180;

/**
 * Four key rates on a shared 0–100 scale.
 *
 * The fill is a RADIAL gradient anchored on the centre, not a flat wash: a long spoke reaches the
 * dense outer stops while a short one only ever exposes the pale inner ones, so "how far this axis
 * reached" is legible from the colour alone.
 *
 * Order the axes so the two extremes are ADJACENT. Four axes with the big values facing each other
 * collapse into a lens, which is a shape rather than a chart.
 */
export function RadarRates({ axes, max = 100, className }: RadarRatesProps) {
  useIsDark(); // re-render on a theme flip so the token colours re-resolve
  const { t, locale } = useI18n();
  const uid = useId().replace(/:/g, "");

  if (axes.length < 3) return null;

  const brand = tokenColor("brand-500");
  const line = tokenColor("line");
  const faint = tokenColor("text-subtle");
  const canvas = tokenColor("surface");

  const angles = spokeAngles(axes.length);
  const at = (i: number, k: number) =>
    [CX + Math.cos(angles[i]) * R * k, CY + Math.sin(angles[i]) * R * k] as const;
  const radii = axes.map((a) => (Math.max(0, Math.min(max, a.value)) / max) * R);
  const shape = rosePath(CX, CY, rosePoints(angles, radii));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={t("chart.ratesLabel")}
      className={className}
    >
      <defs>
        <radialGradient id={`${uid}-fill`} gradientUnits="userSpaceOnUse" cx={CX} cy={CY} r={R}>
          <stop offset="0%" stopColor={brand} stopOpacity=".03" />
          <stop offset="45%" stopColor={brand} stopOpacity=".13" />
          <stop offset="80%" stopColor={brand} stopOpacity=".28" />
          <stop offset="100%" stopColor={brand} stopOpacity=".42" />
        </radialGradient>
      </defs>

      {STEPS.map((k) => (
        <circle key={k} cx={CX} cy={CY} r={R * k} fill="none" stroke={line} strokeWidth="1" />
      ))}

      {axes.map((_, i) => {
        const [x, y] = at(i, 1);
        return (
          <g key={i}>
            <line x1={CX} y1={CY} x2={x} y2={y} stroke={line} strokeWidth="1" />
            {/* The cap marks the AXIS terminus, not the data vertex — it belongs to the scale. */}
            <circle cx={x} cy={y} r="2.6" fill={faint} opacity=".75" />
          </g>
        );
      })}

      <path
        d={shape}
        fill={`url(#${uid}-fill)`}
        stroke={brand}
        strokeWidth="2"
        strokeLinejoin="round"
      />

      {/* Painted AFTER the blob and knocked out of whatever they land on: a scale the shape can
          swallow is not a scale, and the inner rings are exactly the ones it covers. */}
      {STEPS.map((k) => (
        <text
          key={k}
          x={CX + Math.cos(TICK_ANGLE) * R * k + 3}
          y={CY + Math.sin(TICK_ANGLE) * R * k + 3}
          fontSize="8.5"
          fill={faint}
          paintOrder="stroke"
          stroke={canvas}
          strokeWidth="2"
          strokeLinejoin="round"
        >
          {formatNumber(Math.round(max * k))}
        </text>
      ))}

      {axes.map((axis, i) => {
        const [px, py] = at(i, 1);
        return (
          <circle key={i} cx={px} cy={py} r="11" fill="transparent">
            <title>{`${axis.title ?? axis.label} — ${formatNumber(axis.value)}${locale === "fa" ? "٪" : "%"}`}</title>
          </circle>
        );
      })}

      {axes.map((axis, i) => {
        const lx = CX + Math.cos(angles[i]) * (R + 24);
        const ly = CY + Math.sin(angles[i]) * (R + 15);
        // text-anchor is LOGICAL, not physical: under dir="rtl" "start" pins the text's RIGHT edge.
        // Taken literally it hangs both side labels back INTO the chart, over the outer ring and
        // its cap, so the mapping has to flip with the writing direction.
        const rtl = locale === "fa";
        const away = lx > CX ? (rtl ? "end" : "start") : rtl ? "start" : "end";
        return (
          <text
            key={i}
            x={lx}
            y={ly + 3}
            textAnchor={Math.abs(lx - CX) < 12 ? "middle" : away}
            fontSize="10.5"
            fill={faint}
          >
            {axis.label}
          </text>
        );
      })}
    </svg>
  );
}
