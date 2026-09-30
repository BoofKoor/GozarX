import { useId, useRef, useState } from "react";

import { useIsDark } from "@/hooks/useIsDark";
import { dirFor, getLocale } from "@/i18n";
import { seriesColor, tokenColor } from "@/lib/chartTheme";
import { localizeDigits } from "@/lib/format";

import { areaFrom, smoothPath, visibleLabels, type Point } from "./geometry";

export interface TrendSeries {
  /** One value per bucket, oldest first. Every series must be the same length as `labels`. */
  values: number[];
  /** Index into the chart palette (0 = brand). */
  tone?: number;
  /** Name for the hover readout. Omitted hides this series from it. */
  label?: string;
  /** `secondary` plots against `secondaryTicks` and the right-hand axis. */
  axis?: "primary" | "secondary";
}

export interface AreaTrendProps {
  series: TrendSeries[];
  /** Two-line x labels: the day number and, under it, the weekday initial. */
  labels: { primary: string; secondary?: string }[];
  /** Y-axis ticks, in data units. The TOP tick also sets the scale, so the curve never touches it. */
  ticks?: number[];
  /**
   * Ticks for the `secondary` series, drawn on the right. The same COUNT as `ticks`, so both sets
   * land on the same gridlines.
   *
   * Signups run at about 1% of claims. On one shared scale their line was a flat stroke along the
   * floor — a series you could see was there and could not read a single day of.
   */
  secondaryTicks?: number[];
  /**
   * The last bucket is still filling (today). Its segment is drawn DASHED: solid, a day that is
   * four hours old read as a collapse on every chart, every morning.
   */
  partialLast?: boolean;
  /** Said beside the last bucket's date in the hover readout when `partialLast` is set. */
  partialLabel?: string;
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
/** Right padding when a second axis needs its labels there — the same room the left one gets. */
const PAD_R_AXIS = 46;
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
  secondaryTicks,
  partialLast = false,
  partialLabel,
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

  const dual = secondaryTicks != null && series.some((s) => s.axis === "secondary");
  const padR = dual ? PAD_R_AXIS : PAD_R;
  const onSecondary = (s: TrendSeries) => dual && s.axis === "secondary";
  // The TICKS set the ceiling, not the data. Scaling to the data max instead pins the tallest
  // curve to the very top of the plot and pushes the top gridline — which the caller rounded UP to
  // a whole hundred — clean off the canvas, taking its label with it.
  const maxOf = (values: number[], axisTicks: number[] | undefined) =>
    Math.max(1, ...values, ...(axisTicks ?? []));
  const max = maxOf(
    series.filter((s) => !onSecondary(s)).flatMap((s) => s.values),
    ticks,
  );
  const max2 = maxOf(
    series.filter(onSecondary).flatMap((s) => s.values),
    secondaryTicks,
  );
  const plotW = W - PAD_L - padR;
  const px = (i: number) => PAD_L + (i / (count - 1)) * plotW;
  const yOf = (v: number, top: number) => PAD_T + (1 - v / top) * (H - PAD_T - PAD_B);
  const py = (v: number) => yOf(v, max);
  const baseline = H - PAD_B;
  const showLabel = visibleLabels(count, plotW);
  // Where the still-filling last bucket begins: everything right of it is drawn dashed.
  const splitX = partialLast ? px(count - 2) : W;

  const grid = tokenColor("line");
  const faint = tokenColor("text-subtle");
  const shaped = series.map((s, i) => {
    const top = onSecondary(s) ? max2 : max;
    const pts: Point[] = s.values.map((v, j) => [px(j), yOf(v, top)] as Point);
    return { pts, line: smoothPath(pts), color: seriesColor(s.tone ?? i), label: s.label };
  });
  const secondaryColor = shaped[series.findIndex(onSecondary)]?.color;
  // Painted back-to-front so series 0 — the primary metric — lands ON TOP at every crossing.
  const paintOrder = shaped.map((_, i) => i).reverse();

  const named = shaped.map((s, i) => ({ ...s, i })).filter((s) => s.label != null);
  const fmt = formatValue ?? ((v: number) => localizeDigits(String(v)));

  function track(clientX: number) {
    const box = frame.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const rel = ((clientX - box.left) / box.width) * W;
    const i = Math.round(((rel - PAD_L) / plotW) * (count - 1));
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
            x2={W - padR}
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

          {/* Complete buckets on one side of the split, the partial one on the other. */}
          <mask id={`${uid}-done`}>
            <rect x="0" y="0" width={splitX} height={H} fill="#fff" />
          </mask>
          <mask id={`${uid}-partial`}>
            <rect x={splitX} y="0" width={Math.max(0, W - splitX)} height={H} fill="#fff" />
          </mask>
        </defs>

        {(ticks ?? []).map((t, k) => (
          <g key={t}>
            <line
              x1={PAD_L}
              y1={py(t)}
              x2={W - padR}
              y2={py(t)}
              stroke={grid}
              strokeWidth="1"
              opacity=".8"
            />
            {/* Through the same formatter as the readout: «۲۰۰۰۰» without its separator is a
                figure you have to count the zeros of. */}
            <text x={PAD_L - 8} y={py(t) + 4} textAnchor="end" fontSize="11" fill={faint}>
              {fmt(t)}
            </text>
            {dual && secondaryTicks?.[k] != null && (
              <text x={W - padR + 8} y={py(t) + 4} textAnchor="start" fontSize="11" fill={faint}>
                {fmt(secondaryTicks[k])}
              </text>
            )}
          </g>
        ))}
        {/* Which axis belongs to which line: a swatch of each series' colour over its labels.
            The labels themselves stay in the ink tier — series colours are fills, and as type
            they would fall below AA. */}
        {dual && (
          <>
            <circle cx={PAD_L - 14} cy={5} r={3} fill={shaped[0]?.color} />
            {secondaryColor && <circle cx={W - padR + 14} cy={5} r={3} fill={secondaryColor} />}
          </>
        )}

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
          <g mask={partialLast ? `url(#${uid}-done)` : undefined}>
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
          {partialLast && (
            <g mask={`url(#${uid}-partial)`}>
              {paintOrder.map((i) => (
                <path
                  key={i}
                  d={shaped[i].line}
                  fill="none"
                  stroke={shaped[i].color}
                  strokeWidth={i === 0 ? 2.25 : 2}
                  strokeDasharray="4 5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ))}
            </g>
          )}
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

        {labels.map((label, i) =>
          !showLabel[i] ? null : (
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
          ),
        )}
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
          <div
            className="rounded-xl bg-surface px-2.5 py-2 text-xs shadow-raised"
            dir={dirFor(getLocale())}
          >
            {/* Day number and weekday are separate runs: joined into one string the digits and the
                Persian letter reorder around the separator. */}
            <div className="flex items-baseline gap-1.5 font-semibold text-content">
              <span className="tabular-nums">{labels[hover]?.primary}</span>
              {labels[hover]?.secondary && (
                <span className="text-content-subtle">{labels[hover].secondary}</span>
              )}
              {partialLast && partialLabel && hover === count - 1 && (
                <span className="font-normal text-content-subtle">{partialLabel}</span>
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
