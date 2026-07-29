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
      reset: (id: string) => void;
    };
    onTurnstileLoad?: () => void;
  }
}

const SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoad&render=explicit";
const LOAD_TIMEOUT_MS = 8000;

// Resolve once the CF script is ready; REJECT if it errors or never arrives (blocked/filtered
// network — our core audience). Without a reject path the promise hangs forever and the CTA is left
// silently disabled with no explanation. The timeout covers the "script tag added but onload never
// fires" case (a swallowed network error).
function ensureScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.turnstile) return resolve();
    let settled = false;
    const done = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };
    const timer = setTimeout(() => done(reject), LOAD_TIMEOUT_MS);
    window.onTurnstileLoad = () => done(() => (clearTimeout(timer), resolve()));

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener("error", () => done(() => (clearTimeout(timer), reject())));
      return; // onTurnstileLoad (above) or the timeout will settle us
    }
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onerror = () => done(() => (clearTimeout(timer), reject()));
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
  onError,
  resetSignal = 0,
}: {
  siteKey: string;
  locale: Locale;
  onToken: (t: string) => void;
  /** Load failure or a CF error-callback — the parent surfaces a retry instead of a dead button. */
  onError?: () => void;
  /** Bump to imperatively reset the widget after a token is consumed (single-use tokens). */
  resetSignal?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    ensureScript().then(
      () => {
        if (cancelled || !ref.current || !window.turnstile) return;
        widgetId.current = window.turnstile.render(ref.current, {
          sitekey: siteKey,
          callback: (token: string) => onToken(token),
          "error-callback": () => {
            onToken("");
            onError?.();
          },
          "expired-callback": () => onToken(""), // token lapsed — CF re-challenges; not a hard error
          theme: effectiveTheme(),
          language: locale,
          appearance: "interaction-only", // visible only when CF actually needs an interaction
        });
      },
      () => {
        if (!cancelled) onError?.(); // script blocked/timed out — let the parent explain + retry
      },
    );
    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
      widgetId.current = null;
    };
  }, [siteKey, locale, onToken, onError]);

  // Reset the rendered widget when the parent consumed a token (so the next claim gets a fresh one).
  useEffect(() => {
    if (resetSignal > 0 && widgetId.current && window.turnstile) {
      window.turnstile.reset(widgetId.current);
    }
  }, [resetSignal]);

  return <div ref={ref} className="ts-slot" />;
}
