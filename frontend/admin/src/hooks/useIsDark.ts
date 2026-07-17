import { useSyncExternalStore } from "react";

// Reactively track whether the app is in dark mode. Dark mode is driven by the `dark` class on
// <html> (set from localStorage/OS preference in index.html, toggled at runtime by the theme
// switcher). recharts can't read Tailwind's `dark:` variants, so charts subscribe here to pick
// theme-aware colors and re-render the instant the class flips.

function subscribe(callback: () => void): () => void {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

function getSnapshot(): boolean {
  return document.documentElement.classList.contains("dark");
}

export function useIsDark(): boolean {
  // getServerSnapshot returns false — this is a client-only SPA, but React requires the third arg.
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
