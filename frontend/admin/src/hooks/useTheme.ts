import { useCallback } from "react";

import { useIsDark } from "./useIsDark";

export type Theme = "light" | "dark";

/** Apply a theme: flip the `dark` class on <html> (which useIsDark observes) and persist the choice
 *  so index.html's pre-mount bootstrap restores it next visit (no flash). */
function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem("theme", theme);
  } catch {
    /* private mode / storage disabled — the class still applies for this session */
  }
}

/** Read + control the light/dark theme. `isDark` stays reactive via useIsDark, so anything using
 *  this hook (and the charts) re-render the instant the theme flips. */
export function useTheme() {
  const isDark = useIsDark();
  const setTheme = useCallback((t: Theme) => applyTheme(t), []);
  const toggle = useCallback(() => applyTheme(isDark ? "light" : "dark"), [isDark]);
  return { theme: (isDark ? "dark" : "light") as Theme, isDark, setTheme, toggle };
}
