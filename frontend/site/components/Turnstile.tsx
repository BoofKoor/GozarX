"use client";

import { useEffect, useRef } from "react";
import type { Locale } from "@/lib/i18n";

// Cloudflare Turnstile — rendered ONLY when the backend reports it configured (config.turnstile_
// enabled). In dev the site key is empty and this never mounts, so the claim flow works without it.
// The widget follows the SITE's theme + locale (not the browser's) and runs `interaction-only`, so
// it stays invisible unless Cloudflare actually needs the user — matching the card's "protected by
// an invisible check" caption instead of parking a white box in the dark card.
declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      remove: (id: string) => void;
    };
    onTurnstileLoad?: () => void;
  }
}

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoad&render=explicit";

function ensureScript(): Promise<void> {
  return new Promise((resolve) => {
    if (window.turnstile) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
    window.onTurnstileLoad = () => resolve();
    if (existing) return;
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    document.head.appendChild(s);
  });
}

/** The page's EFFECTIVE theme: an explicit data-theme choice wins, else the OS preference. */
function effectiveTheme(): "light" | "dark" {
  const attr = document.getElementById("app")?.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function Turnstile({
  siteKey,
  locale,
  onToken,
}: {
  siteKey: string;
  locale: Locale;
  onToken: (t: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void ensureScript().then(() => {
      if (cancelled || !ref.current || !window.turnstile) return;
      widgetId.current = window.turnstile.render(ref.current, {
        sitekey: siteKey,
        callback: (token: string) => onToken(token),
        "error-callback": () => onToken(""),
        "expired-callback": () => onToken(""),
        theme: effectiveTheme(),
        language: locale,
        appearance: "interaction-only", // visible only when CF actually needs an interaction
      });
    });
    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
    };
  }, [siteKey, locale, onToken]);

  return <div ref={ref} className="ts-slot" />;
}
