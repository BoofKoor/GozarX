"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";

// The visitor's two display preferences, each with ONE implementation. The header, the phone menu,
// the footer and the account page's settings each carried their own copy of "set the cookie, set
// the attributes, refresh" (C-25), and the two theme toggles could disagree about what was on.

const YEAR = 400 * 24 * 3600;

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${YEAR}; samesite=lax`;
}

function clearCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0; samesite=lax`;
}

// ── theme ─────────────────────────────────────────────────────────────────────────────────────
// Three states (decision D6, C-19): "system" follows the device and is the default; "light" and
// "dark" are explicit choices. Before, choosing either one was permanent — there was no way back
// to following the device short of clearing cookies. "system" is the ABSENCE of a choice: no
// cookie and no `data-theme`, which is exactly the state the stylesheet's auto blocks answer.

export type ThemeChoice = "system" | "light" | "dark";
export type Theme = "light" | "dark";

const THEME_EVENT = "gz:theme";
const DARK_MQ = "(prefers-color-scheme: dark)";

function readChoice(): ThemeChoice {
  const attr = document.getElementById("app")?.getAttribute("data-theme");
  return attr === "light" || attr === "dark" ? attr : "system";
}

function readEffective(): Theme {
  const choice = readChoice();
  if (choice !== "system") return choice;
  return window.matchMedia(DARK_MQ).matches ? "dark" : "light";
}

function subscribeTheme(onChange: () => void): () => void {
  const mq = window.matchMedia(DARK_MQ);
  window.addEventListener(THEME_EVENT, onChange);
  mq.addEventListener("change", onChange);
  return () => {
    window.removeEventListener(THEME_EVENT, onChange);
    mq.removeEventListener("change", onChange);
  };
}

export function applyTheme(choice: ThemeChoice) {
  const targets = [document.documentElement, document.getElementById("app")];
  if (choice === "system") {
    clearCookie("theme");
    for (const el of targets) el?.removeAttribute("data-theme");
  } else {
    setCookie("theme", choice);
    for (const el of targets) el?.setAttribute("data-theme", choice);
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

/** The visitor's theme choice and what it currently resolves to, kept in sync across every
 *  control on the page (and with the device, while the choice is "system"). The pages are
 *  prerendered, so the HTML cannot know the choice: it is always drawn as "system", the inline
 *  script in the root layout puts the saved `data-theme` on before the first paint, and these
 *  controls read it right after hydration. */
export function useTheme(): {
  choice: ThemeChoice;
  effective: Theme;
  setChoice: (next: ThemeChoice) => void;
} {
  const choice = useSyncExternalStore(subscribeTheme, readChoice, () => "system" as ThemeChoice);
  const effective = useSyncExternalStore(subscribeTheme, readEffective, () => "light" as Theme);
  const setChoice = useCallback((next: ThemeChoice) => applyTheme(next), []);
  return { choice, effective, setChoice };
}

// ── language ──────────────────────────────────────────────────────────────────────────────────

/** Switch the site's language: set the cookie `proxy.ts` reads, then load the page again. Each
 *  language is its own prerendered tree (`app/[lang]`), so this is a different ROOT layout — a
 *  full load, not a soft refresh, which would try to patch one language's tree into the other's. */
export function useLocaleSwitch(locale: Locale): (next: Locale) => void {
  return useCallback(
    (next: Locale) => {
      if (next === locale) return;
      setCookie("locale", next);
      window.location.reload();
    },
    [locale],
  );
}
