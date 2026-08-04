import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { MESSAGES, type MessageKey } from "./messages";

export type Locale = "fa" | "en";

const STORAGE_KEY = "locale";
const TAGS: Record<Locale, string> = { fa: "fa-IR", en: "en-US" };

/**
 * The active locale, also readable OUTSIDE React.
 *
 * `lib/format.ts` needs it from ~140 call sites that are plain functions, not hooks. Keeping one
 * module-level value that the provider writes lets those stay plain calls; the provider's state is
 * what re-renders the tree, so the two never disagree for a frame.
 */
let current: Locale = "fa";

export function getLocale(): Locale {
  return current;
}

/** The BCP-47 tag for `Intl` — the panel's locales are the only two that matter. */
export function localeTag(): string {
  return TAGS[current];
}

export function readStoredLocale(): Locale {
  try {
    return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "fa";
  } catch {
    return "fa"; // private mode / storage disabled
  }
}

/** Writing direction follows the locale — this is the one place that mapping lives. */
export function dirFor(locale: Locale): "rtl" | "ltr" {
  return locale === "fa" ? "rtl" : "ltr";
}

function applyLocale(locale: Locale): void {
  current = locale;
  const el = document.documentElement;
  el.lang = locale;
  el.dir = dirFor(locale);
  // The browser TAB is user-facing too, and index.html can only ship one language.
  document.title = translate(locale, "shell.documentTitle");
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* the attributes still applied for this session */
  }
}

/** Substitute `{token}` placeholders, and only the ones actually supplied. */
function render(template: string, tokens?: Record<string, string | number>): string {
  if (!tokens) return template;
  return template.replace(/\{(\w+)\}/g, (whole, key: string) =>
    key in tokens ? String(tokens[key]) : whole,
  );
}

export function translate(
  locale: Locale,
  key: MessageKey,
  tokens?: Record<string, string | number>,
): string {
  // A missing English string cannot happen (messages.ts types EN against FA), but a stale key from
  // a hot reload can — falling back to the key beats rendering "undefined" into the page.
  const table = MESSAGES[locale] as Record<string, string>;
  return render(table[key] ?? key, tokens);
}

/**
 * Translate OUTSIDE a component — a class error boundary, an axios interceptor, a recharts prop
 * factory. Same escape hatch `lib/format` uses: it reads the module-level locale rather than
 * subscribing to it, so it does not re-render on a language switch. Components use `useI18n().t`.
 */
export function t(key: MessageKey, tokens?: Record<string, string | number>): string {
  return translate(getLocale(), key, tokens);
}

export interface I18n {
  locale: Locale;
  dir: "rtl" | "ltr";
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, tokens?: Record<string, string | number>) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const stored = readStoredLocale();
    applyLocale(stored); // index.html sets fa/rtl up front; honour a stored English choice here
    return stored;
  });

  const setLocale = useCallback((next: Locale) => {
    applyLocale(next);
    setLocaleState(next);
  }, []);

  const value = useMemo<I18n>(
    () => ({
      locale,
      dir: dirFor(locale),
      setLocale,
      t: (key, tokens) => translate(locale, key, tokens),
    }),
    [locale, setLocale],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (ctx) return ctx;
  // Tests render components in isolation; falling back to the stored locale keeps them mountable
  // without every test file wrapping in a provider.
  const locale = getLocale();
  return {
    locale,
    dir: dirFor(locale),
    setLocale: applyLocale,
    t: (key, tokens) => translate(locale, key, tokens),
  };
}

export type { MessageKey };
