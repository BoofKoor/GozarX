import { useId } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { seriesColor, tokenColor } from "@/lib/chartTheme";
import { localizeDigits } from "@/lib/format";

import { areaFrom, smoothPath, type Point } from "./geometry";

export interface TrendSeries {
  /** One value per bucket, oldest first. Every series must be the same length as `labels`. */
  values: number[];
  /** Index into the chart palette (0 = brand). */
  tone?: number;
}

export interface AreaTrendProps {
  series: TrendSeries[];
  /** Two-line x labels: the day number and, under it, the weekday initial. */
  labels: { primary: string; secondary?: string }[];
  /** Y-axis ticks, in data units. */
  ticks?: number[];
  ariaLabel: string;
  className?: string;
}

const W = 760;
const H = 260;
const PAD_L = 42;
const PAD_R = 14;
const PAD_T = 12;
const PAD_B = 38;

/**
 * The dashboard's main trend, drawn by hand rather than with recharts.
 *
 * recharts can express neither of the two things this chart is for:
 *
 * 1. The FILL exists only over the tail of the range and dissolves backwards, so older days stay
 *    clean lines and the visual weight lands on recent activity.
 * 2. The LINES fade in AT the y-axis. The window is a slice of a longer series, and a line that
 *    starts exactly on the axis hides that — it reads as the moment the data began.
 *
 * Both are luminance masks (black hides, white shows) over a group, which is the only way to fade
 * part of a stroked path without also fading its colour into the background.
 */
export function AreaTrend({ series, labels, ticks, ariaLabel, className }: AreaTrendProps) {
  useIsDark(); // re-render on a theme flip so the token colours re-resolve
  const uid = useId().replace(/:/g, "");

  const points = series.map((s) => s.values);
  if (points.length === 0 || points[0].length < 2) return null;

  const max = Math.max(1, ...points.flat());
  const px = (i: number) => PAD_L + (i / (points[0].length - 1)) * (W - PAD_L - PAD_R);
  const py = (v: number) => PAD_T + (1 - v / max) * (H - PAD_T - PAD_B);
  const baseline = H - PAD_B;

  const grid = tokenColor("line");
  const faint = tokenColor("text-subtle");
  const shaped = series.map((s, i) => {
    const pts: Point[] = s.values.map((v, j) => [px(j), py(v)] as Point);
    return { pts, line: smoothPath(pts), color: seriesColor(s.tone ?? i) };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} className={className}>
      <defs>
        {shaped.map((s, i) => (
          <linearGradient
            key={i}
            id={`${uid}-fill-${i}`}
            gradientUnits="userSpaceOnUse"
            x1="0"
            y1={PAD_T}
            x2="0"
            y2={baseline}
          >
            <stop offset="0%" stopColor={s.color} stopOpacity={i === 0 ? 0.1 : 0.07} />
            <stop offset="100%" stopColor={s.color} stopOpacity="0" />
          </linearGradient>
        ))}

        <linearGradient
          id={`${uid}-tail`}
          gradientUnits="userSpaceOnUse"
          x1={PAD_L}
          y1="0"
          x2={W - PAD_R}
          y2="0"
        >
          <stop offset="0%" stopColor="#000" />
          <stop offset="58%" stopColor="#000" />
          <stop offset="100%" stopColor="#fff" />
        </linearGradient>
        <mask id={`${uid}-tailMask`}>
          <rect x="0" y="0" width={W} height={H} fill={`url(#${uid}-tail)`} />
        </mask>

        <linearGradient
          id={`${uid}-head`}
          gradientUnits="userSpaceOnUse"
          x1={PAD_L}
          y1="0"
          x2={PAD_L + 90}
          y2="0"
        >
          <stop offset="0%" stopColor="#000" />
          <stop offset="100%" stopColor="#fff" />
        </linearGradient>
        <mask id={`${uid}-headMask`}>
          <rect x="0" y="0" width={W} height={H} fill={`url(#${uid}-head)`} />
        </mask>
      </defs>

      {(ticks ?? []).map((t) => (
        <g key={t}>
          <line x1={PAD_L} y1={py(t)} x2={W - PAD_R} y2={py(t)} stroke={grid} strokeWidth="1" />
          <text x={PAD_L - 8} y={py(t) + 4} textAnchor="end" fontSize="11" fill={faint}>
            {localizeDigits(String(t))}
          </text>
        </g>
      ))}

      <g mask={`url(#${uid}-tailMask)`}>
        {shaped.map((s, i) => (
          <path key={i} d={areaFrom(s.line, s.pts, baseline)} fill={`url(#${uid}-fill-${i})`} />
        ))}
      </g>

      <g mask={`url(#${uid}-headMask)`}>
        {shaped.map((s, i) => (
          <path
            key={i}
            d={s.line}
            fill="none"
            stroke={s.color}
            strokeWidth={i === 0 ? 2.75 : 2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </g>

      {shaped.map((s, i) => {
        const end = s.pts[s.pts.length - 1];
        return (
          <circle
            key={i}
            cx={end[0]}
            cy={end[1]}
            r="3.5"
            fill={s.color}
            className="stroke-surface-sunken"
            strokeWidth="2"
          />
        );
      })}

      {labels.map((label, i) => (
        <g key={i}>
          <text x={px(i)} y={H - 17} textAnchor="middle" fontSize="11.5" fill={faint}>
            {label.primary}
          </text>
          {label.secondary && (
            <text x={px(i)} y={H - 4} textAnchor="middle" fontSize="9.5" fill={faint} opacity=".65">
              {label.secondary}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
