// Theme-aware colours for recharts, which can't read Tailwind's `dark:` variants or the token
// classes. Everything here resolves the SAME CSS custom properties the rest of the panel uses
// (src/styles/tokens.css) at call time, so charts follow a retheme automatically instead of
// carrying their own hardcoded hex values. Pair with `useIsDark()` — the hook re-renders on a theme
// flip, which is what makes these values re-resolve.

/** Read a raw `R G B` token and return a usable CSS colour. `alpha` < 1 produces `rgb(r g b / a)`. */
export function tokenColor(name: string, alpha = 1): string {
  const channels =
    typeof window === "undefined"
      ? ""
      : getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  // Fallback keeps charts renderable in jsdom (tests) where custom properties don't resolve.
  const rgb = channels || "100 116 139";
  return alpha >= 1 ? `rgb(${rgb})` : `rgb(${rgb} / ${alpha})`;
}

/** The categorical series palette, in order. Chart 1 is the brand so the primary metric reads as
 *  "ours"; the rest stay distinguishable in both themes and for common colour-vision deficiencies. */
export const CHART_TOKENS = [
  "chart-1",
  "chart-2",
  "chart-3",
  "chart-4",
  "chart-5",
  "chart-6",
] as const;

export function seriesColor(i: number, alpha = 1): string {
  const idx = ((i % CHART_TOKENS.length) + CHART_TOKENS.length) % CHART_TOKENS.length;
  return tokenColor(CHART_TOKENS[idx], alpha);
}

export interface ChartTheme {
  grid: string;
  axis: string;
  brand: string;
  accent: string;
  tooltip: {
    contentStyle: React.CSSProperties;
    labelStyle: React.CSSProperties;
    itemStyle: React.CSSProperties;
    cursor: { fill: string };
  };
}

/** `isDark` is not read directly — it exists so callers pass a value that changes on a theme flip,
 *  forcing this to re-run and re-resolve the custom properties. */
export function chartTheme(_isDark: boolean): ChartTheme {
  const grid = tokenColor("line");
  const axis = tokenColor("text-subtle");
  const text = tokenColor("text");
  return {
    grid,
    axis,
    brand: tokenColor("chart-1"),
    accent: tokenColor("chart-2"),
    tooltip: {
      contentStyle: {
        borderRadius: 12,
        border: `1px solid ${grid}`,
        background: tokenColor("surface"),
        color: text,
        fontSize: 12,
        boxShadow: "var(--shadow-raised)",
        direction: "rtl",
      },
      labelStyle: { color: text, fontWeight: 600 },
      itemStyle: { color: text },
      cursor: { fill: tokenColor("text", 0.06) },
    },
  };
}
