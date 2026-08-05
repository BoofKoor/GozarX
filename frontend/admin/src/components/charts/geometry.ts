/**
 * Path maths for the three hand-drawn charts.
 *
 * These live outside the components because they are the part worth testing: a curve that overshoots
 * its own data, or a rose whose "waist" is not actually a waist, is a defect you can only catch by
 * reading pixels — or by asserting the geometry here.
 */

export type Point = readonly [number, number];

/**
 * A smooth open curve through `pts` (Catmull-Rom converted to cubic Béziers).
 *
 * `tension` is the handle length as a fraction of the neighbour span; 1/6 reproduces the classic
 * uniform Catmull-Rom. Endpoints reflect their neighbour so the curve starts and ends on the data
 * instead of drifting off it.
 */
export function smoothPath(pts: readonly Point[], tension = 1 / 6): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M${pts[0][0]},${pts[0][1]}`;
  const at = (i: number): Point => pts[Math.max(0, Math.min(pts.length - 1, i))];
  let d = `M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = at(i - 1);
    const p1 = at(i);
    const p2 = at(i + 1);
    const p3 = at(i + 2);
    const c1: Point = [p1[0] + (p2[0] - p0[0]) * tension, p1[1] + (p2[1] - p0[1]) * tension];
    const c2: Point = [p2[0] - (p3[0] - p1[0]) * tension, p2[1] - (p3[1] - p1[1]) * tension];
    d +=
      `C${c1[0].toFixed(2)},${c1[1].toFixed(2)} ` +
      `${c2[0].toFixed(2)},${c2[1].toFixed(2)} ` +
      `${p2[0].toFixed(2)},${p2[1].toFixed(2)}`;
  }
  return d;
}

/** Close a line path down to a baseline, producing the area under it. */
export function areaFrom(line: string, pts: readonly Point[], baseline: number): string {
  if (pts.length === 0) return "";
  const last = pts[pts.length - 1][0].toFixed(2);
  const first = pts[0][0].toFixed(2);
  return `${line}L${last},${baseline}L${first},${baseline}Z`;
}

/**
 * The whole region below a line, out to the FRAME's edges — a clip region, not an area fill.
 *
 * `areaFrom` closes straight down from the first and last data points, which leaves the side
 * padding outside the region. Anything clipped to it therefore gets sliced by that diagonal, and a
 * marker band under the first or last day tapers into a teardrop. Here the curve is extended
 * horizontally at its own end heights first, so the region spans `0…width` and the band keeps its
 * full thickness wherever the marked day falls.
 */
export function underCurve(
  line: string,
  pts: readonly Point[],
  width: number,
  height: number,
): string {
  if (pts.length === 0) return "";
  const [, firstY] = pts[0];
  const [, lastY] = pts[pts.length - 1];
  return (
    `M0,${firstY.toFixed(2)}L${line.slice(1)}` +
    `L${width},${lastY.toFixed(2)}L${width},${height}L0,${height}Z`
  );
}

export interface RosePoint {
  /** Angle in radians, screen space (y grows downward). */
  a: number;
  r: number;
}

/**
 * Turn N data radii into 2N points: the data vertices plus a WAIST on each diagonal between them.
 *
 * N points alone can only draw a convex outline — tangential handles bulge the curve out toward a
 * circular arc or flatten it onto the chord, but never past it — so the inward arcs a radar wants
 * between its lobes are unreachable by construction, not by tuning.
 *
 * Each waist radius comes from the CHORD it sits on: for two axes a quarter-turn apart at radii
 * `a` and `b`, the straight line between them crosses the diagonal at `a·b·√2/(a+b)`. Deriving it
 * that way makes the indentation follow its two neighbours instead of being a fixed inset.
 * `waist` scales it: below 1.0 the shape passes inside the chord and reads as a star; above ~1.10
 * the indentation disappears into a plain blob.
 */
export function rosePoints(angles: readonly number[], radii: readonly number[], waist = 1.03) {
  const n = angles.length;
  const out: RosePoint[] = [];
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const a = radii[i];
    const b = radii[j];
    out.push({ a: angles[i], r: a });
    out.push({
      a: angles[i] + Math.PI / n,
      r: ((a * b * Math.SQRT2) / (a + b || 1)) * waist,
    });
  }
  return out;
}

/**
 * A closed curve through points that alternate radial maxima and minima.
 *
 * Handles are TANGENTIAL — perpendicular to each point's own spoke — which is not an approximation
 * here: on a smooth closed curve the tangent at a radial extremum genuinely is perpendicular to the
 * radius, and every point `rosePoints` emits is one.
 *
 * Handle LENGTH comes from the SEGMENT, not from the point's own radius. Tying it to the radius is
 * what makes a short axis next to a long one read as a sharp corner: it holds its tangent for ten
 * pixels and then strikes out for a point three times further away. `k = 0.34` is the circle-exact
 * ratio for 45° spans, so with four axes every vertex rounds by the same amount.
 */
export function rosePath(cx: number, cy: number, pts: readonly RosePoint[], k = 0.34): string {
  const n = pts.length;
  if (n === 0) return "";
  const P: Point[] = pts.map((p) => [cx + Math.cos(p.a) * p.r, cy + Math.sin(p.a) * p.r]);
  const T: Point[] = pts.map((p) => [-Math.sin(p.a), Math.cos(p.a)]);
  let d = `M${P[0][0].toFixed(2)},${P[0][1].toFixed(2)}`;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const len = Math.hypot(P[j][0] - P[i][0], P[j][1] - P[i][1]) * k;
    const c1: Point = [P[i][0] + T[i][0] * len, P[i][1] + T[i][1] * len];
    const c2: Point = [P[j][0] - T[j][0] * len, P[j][1] - T[j][1] * len];
    d +=
      `C${c1[0].toFixed(2)},${c1[1].toFixed(2)} ` +
      `${c2[0].toFixed(2)},${c2[1].toFixed(2)} ` +
      `${P[j][0].toFixed(2)},${P[j][1].toFixed(2)}`;
  }
  return `${d}Z`;
}

/** Evenly spaced angles starting at twelve o'clock, going clockwise in screen space. */
export function spokeAngles(n: number): number[] {
  return Array.from({ length: n }, (_, i) => (i / n) * Math.PI * 2 - Math.PI / 2);
}
