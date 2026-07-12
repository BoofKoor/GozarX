"use client";

// PWA install state — a tiny external store so the reward chips can offer a REAL install (not a
// decorative button). We capture the Chromium `beforeinstallprompt` event (which fires once, early),
// listen for `appinstalled`, and detect an already-installed (standalone) launch. iOS Safari has no
// install event, so there we surface the manual "Add to Home Screen" steps instead.

import { useSyncExternalStore } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export type PwaState = "installed" | "installable" | "ios" | "unsupported";

let deferred: BeforeInstallPromptEvent | null = null;
let installed = false;
let started = false;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches === true ||
    (window.navigator as { standalone?: boolean }).standalone === true // iOS Safari
  );
}

function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  return /iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
}

// Wire the global listeners exactly once. Called at module load (client) AND from PwaRegister, so
// the one-shot `beforeinstallprompt` is never missed regardless of mount timing. Idempotent.
export function initPwa(): void {
  if (started || typeof window === "undefined") return;
  started = true;
  if (isStandalone()) installed = true;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); // stash it — we drive the prompt from the reward chip
    deferred = e as BeforeInstallPromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    installed = true;
    deferred = null;
    emit();
  });
}

function snapshot(): PwaState {
  if (installed || isStandalone()) return "installed";
  if (deferred) return "installable";
  if (isIOS()) return "ios";
  return "unsupported";
}

// SSR / pre-hydration value: nothing is known server-side, so treat as unsupported until the client
// store settles (avoids a hydration mismatch on the chip).
function serverSnapshot(): PwaState {
  return "unsupported";
}

export function usePwaState(): PwaState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    snapshot,
    serverSnapshot,
  );
}

// Fire the native install prompt. Resolves true ONLY if the user actually accepted the install —
// the caller grants the reward only then. The deferred event is consumed AFTER the choice resolves
// (in `finally`), so the chip stays in `installable` (busy) during the OS prompt instead of
// unmounting mid-prompt; it only clears once the prompt is done.
export async function promptInstall(): Promise<boolean> {
  const evt = deferred;
  if (!evt) return false;
  try {
    await evt.prompt();
    const choice = await evt.userChoice;
    return choice.outcome === "accepted";
  } catch {
    return false;
  } finally {
    deferred = null;
    emit();
  }
}

// Capture as early as possible (module load on the client). PwaRegister also calls this.
initPwa();
