"use client";

import { createContext, createElement, useCallback, useContext, type ReactNode } from "react";
import type { Translator } from "@/lib/i18n";

// The copy a component in the BROWSER reads: one locale, every key already resolved on the server
// (panel overrides included) by `lib/copy`'s `clientCopy`, and handed down once by the root layout.
// It rides in the page's server payload rather than in the JavaScript bundle, which carried both
// locales' full dictionaries to every visitor (C-56) — and it now carries the panel's overrides to
// every client component, where before only the ones the homepage passed `copy` to saw them.
const CopyContext = createContext<Record<string, string>>({});

export function CopyProvider({ copy, children }: { copy: Record<string, string>; children: ReactNode }) {
  return createElement(CopyContext.Provider, { value: copy }, children);
}

/** The translator for client components: a key it does not know comes back as itself, as before. */
export function useT(): Translator {
  const copy = useContext(CopyContext);
  return useCallback((key: string) => copy[key] ?? key, [copy]);
}
