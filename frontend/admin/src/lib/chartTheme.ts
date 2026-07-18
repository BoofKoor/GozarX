// Theme-aware colors for recharts (which can't read Tailwind's `dark:` variants). Values are the
// slate ramp used across the panel so charts match their surrounding cards in both themes. Pair with
// `useIsDark()` and spread `tooltipProps` onto <Tooltip/> so tooltips aren't white boxes in the dark.

// One categorical series palette for every chart (brand green first, then the semantic tokens plus a
// couple of extras). Using a single ordered palette keeps donuts, bars and legends consistent instead
// of each chart inventing its own off-token colors.
export const CHART_COLORS = [
  "#7CB000", // brand
  "#0ea5e9", // info
  "#f59e0b", // warning
  "#a855f7", // violet
  "#14b8a6", // teal
  "#ef4444", // danger
  "#64748b", // slate
  "#ec4899", // pink
] as const;

export function seriesColor(i: number): string {
  return CHART_COLORS[((i % CHART_COLORS.length) + CHART_COLORS.length) % CHART_COLORS.length];
}

export interface ChartTheme {
  grid: string;
  axis: string;
  tooltip: {
    contentStyle: React.CSSProperties;
    labelStyle: React.CSSProperties;
    itemStyle: React.CSSProperties;
  };
}

export function chartTheme(isDark: boolean): ChartTheme {
  const grid = isDark ? "#1e293b" : "#e2e8f0"; // slate-800 / slate-200
  const axis = isDark ? "#64748b" : "#94a3b8"; // slate-500 / slate-400
  const bg = isDark ? "#0f172a" : "#ffffff"; // slate-950 / white
  const text = isDark ? "#e2e8f0" : "#0f172a"; // slate-200 / slate-900
  return {
    grid,
    axis,
    tooltip: {
      contentStyle: {
        borderRadius: 12,
        border: `1px solid ${grid}`,
        background: bg,
        color: text,
        fontSize: 12,
        boxShadow: isDark
          ? "0 4px 12px -2px rgb(0 0 0 / 0.5)"
          : "0 4px 12px -2px rgb(15 23 42 / 0.1)",
      },
      labelStyle: { color: text, fontWeight: 600 },
      itemStyle: { color: text },
    },
  };
}
