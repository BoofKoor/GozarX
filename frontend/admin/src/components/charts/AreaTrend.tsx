import { useId, useRef, useState } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { seriesColor, tokenColor } from "@/lib/chartTheme";
import { localizeDigits } from "@/lib/format";

import { areaFrom, smoothPath, type Point } from "./geometry";

export interface TrendSeries {
  /** One value per bucket, oldest first. Every series must be the same length as `labels`. */
  values: number[];
  /** Index into the chart palette (0 = brand). */
  tone?: number;
  /** Name for the hover readout. Omitted hides this series from it. */
  label?: string;
}

export interface AreaTrendProps {
  series: TrendSeries[];
  /** Two-line x labels: the day number and, under it, the weekday initial. */
  labels: { primary: string; secondary?: string }[];
  /** Y-axis ticks, in data units. The TOP tick also sets the scale, so the curve never touches it. */
  ticks?: number[];
  /** Formats a value for the hover readout. Defaults to the locale's digits. */
  formatValue?: (v: number) => string;
  ariaLabel: string;
  className?: string;
}

// The design's own plot geometry. Everything inside is expressed in these units — tick text at 11,
// day labels at 11.5, strokes at 2 and 2.25 — so the box has to keep the proportions they were
// balanced against, and the SVG then scales to whatever width the column gives it.
const W = 900;
const H = 292;
const PAD_L = 46;
const PAD_R = 16;
const PAD_T = 16;
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
export function AreaTrend({
  series,
  labels,
  ticks,
  formatValue,
  ariaLabel,
  className,
}: AreaTrendProps) {
  useIsDark(); // re-render on a theme flip so the token colours re-resolve
  const uid = useId().replace(/:/g, "");
  const frame = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const points = series.map((s) => s.values);
  const count = points[0]?.length ?? 0;
  if (points.length === 0 || count < 2) return null;

  // The TICKS set the ceiling, not the data. Scaling to the data max instead pins the tallest
  // curve to the very top of the plot and pushes the top gridline — which the caller rounded UP to
  // a whole hundred — clean off the canvas, taking its label with it.
  const max = Math.max(1, ...points.flat(), ...(ticks ?? []));
  const px = (i: number) => PAD_L + (i / (count - 1)) * (W - PAD_L - PAD_R);
  const py = (v: number) => PAD_T + (1 - v / max) * (H - PAD_T - PAD_B);
  const baseline = H - PAD_B;

  const grid = tokenColor("line");
  const faint = tokenColor("text-subtle");
  const shaped = series.map((s, i) => {
    const pts: Point[] = s.values.map((v, j) => [px(j), py(v)] as Point);
    return { pts, line: smoothPath(pts), color: seriesColor(s.tone ?? i), label: s.label };
  });
  // Painted back-to-front so series 0 — the primary metric — lands ON TOP at every crossing.
  const paintOrder = shaped.map((_, i) => i).reverse();

  const named = shaped.map((s, i) => ({ ...s, i })).filter((s) => s.label != null);
  const fmt = formatValue ?? ((v: number) => localizeDigits(String(v)));

  function track(clientX: number) {
    const box = frame.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const rel = ((clientX - box.left) / box.width) * W;
    const i = Math.round(((rel - PAD_L) / (W - PAD_L - PAD_R)) * (count - 1));
    setHover(Math.max(0, Math.min(count - 1, i)));
  }

  return (
    // The time axis reads oldest → newest LEFT to RIGHT even in the RTL panel, so the frame that
    // positions the readout has to be LTR too or the tip lands on the mirrored day.
    <div ref={frame} className={`relative ${className ?? ""}`} dir="ltr">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={ariaLabel}
        className="block h-auto w-full"
        onPointerMove={(e) => track(e.clientX)}
        onPointerLeave={() => setHover(null)}
      >
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
              <stop offset="0%" stopColor={s.color} stopOpacity={i === 0 ? 0.26 : 0.18} />
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
            <line
              x1={PAD_L}
              y1={py(t)}
              x2={W - PAD_R}
              y2={py(t)}
              stroke={grid}
              strokeWidth="1"
              opacity=".8"
            />
            <text x={PAD_L - 8} y={py(t) + 4} textAnchor="end" fontSize="11" fill={faint}>
              {localizeDigits(String(t))}
            </text>
          </g>
        ))}

        <g mask={`url(#${uid}-tailMask)`}>
          {paintOrder.map((i) => (
            <path
              key={i}
              d={areaFrom(shaped[i].line, shaped[i].pts, baseline)}
              fill={`url(#${uid}-fill-${i})`}
            />
          ))}
        </g>

        {hover != null && (
          <line
            x1={px(hover)}
            y1={PAD_T}
            x2={px(hover)}
            y2={baseline}
            stroke={faint}
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )}

        <g mask={`url(#${uid}-headMask)`}>
          {paintOrder.map((i) => (
            <path
              key={i}
              d={shaped[i].line}
              fill="none"
              stroke={shaped[i].color}
              strokeWidth={i === 0 ? 2.25 : 2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
        </g>

        {paintOrder.map((i) => {
          const end = shaped[i].pts[shaped[i].pts.length - 1];
          return (
            <circle
              key={i}
              cx={end[0]}
              cy={end[1]}
              r="3.5"
              fill={shaped[i].color}
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
              <text
                x={px(i)}
                y={H - 4}
                textAnchor="middle"
                fontSize="9.5"
                fill={faint}
                opacity=".65"
              >
                {label.secondary}
              </text>
            )}
          </g>
        ))}
      </svg>

      {hover != null && named.length > 0 && (
        // Positioned in PERCENTAGES of the viewBox so it tracks the chart at any rendered size,
        // and nudged off the point so it never sits under the cursor. The POSITIONED element stays
        // in the frame's LTR direction — `inset-inline-start` resolves against an element's OWN
        // direction, so marking this one RTL would send it to the opposite edge. The RTL text
        // lives one level in.
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full"
          style={{
            // Clamped so the tip stays inside the frame at the first and last day, where half of
            // it would otherwise hang outside the chart.
            insetInlineStart: `${Math.min(Math.max((px(hover) / W) * 100, 9), 91)}%`,
            top: `${(Math.min(...shaped.map((s) => s.pts[hover][1])) / H) * 100}%`,
            marginTop: "-0.5rem",
          }}
        >
          <div className="rounded-xl bg-surface px-2.5 py-2 text-xs shadow-raised" dir="rtl">
            {/* Day number and weekday are separate runs: joined into one string the digits and the
                Persian letter reorder around the separator. */}
            <div className="flex items-baseline gap-1.5 font-semibold text-content">
              <span className="tabular-nums">{labels[hover]?.primary}</span>
              {labels[hover]?.secondary && (
                <span className="text-content-subtle">{labels[hover].secondary}</span>
              )}
            </div>
            {named.map((s) => (
              <div
                key={s.i}
                className="mt-1 flex items-center gap-1.5 whitespace-nowrap text-content-muted"
              >
                <i
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: s.color }}
                  aria-hidden
                />
                <span className="font-semibold tabular-nums text-content">
                  {fmt(series[s.i].values[hover])}
                </span>
                <span>{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
