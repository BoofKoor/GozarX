import { useSyncExternalStore } from "react";

/**
 * Whether the operator has asked their system for less motion.
 *
 * `index.css` already honours this for CSS animations, but recharts animates in JAVASCRIPT
 * (react-smooth drives a clip rect from zero width with `requestAnimationFrame`), so the media query
 * never reaches it and every chart still swept in. Two consequences, one for the operator and one
 * for us: a console full of moving charts for someone who asked for stillness, and — because that
 * animation only advances on real frames — a chart that renders as an EMPTY GRID in any headless
 * capture, geometry present in the DOM and nothing painted. `docs/panel/shot.py` renders with
 * reduced motion for exactly that reason.
 */
const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(callback: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getSnapshot(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

/**
 * Props for a recharts series (`<Area>` / `<Line>` / `<Bar>` / `<Pie>`), so one spread carries the
 * preference to all of them instead of thirteen call sites each remembering.
 */
export function useSeriesAnimation(): { isAnimationActive: boolean } {
  return { isAnimationActive: !useReducedMotion() };
}
