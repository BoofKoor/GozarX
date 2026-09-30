"use client";

import { useEffect, useState } from "react";

/** True once `deadline` (client-clock ms) has passed; re-evaluates by itself at that moment. */
export function useExpired(deadline: number | null): boolean {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (deadline == null) return;
    const ms = deadline - Date.now();
    if (ms <= 0) return;
    const id = window.setTimeout(() => setTick((n) => n + 1), ms + 50);
    return () => window.clearTimeout(id);
  }, [deadline]);
  return deadline != null && deadline <= Date.now();
}

const BACKOFF = [0, 2000, 4000, 8000, 15000, 30000];

/**
 * While `active`, call `run` right away and then again on a growing delay (capped at 30s) — for a
 * deadline that has passed but whose consequence the server hasn't reported yet (a cooldown that
 * should have lifted, a config that should have ended). Stops the moment `active` turns false, so
 * the caller expresses "until the state changes" by deriving `active` from that state.
 */
export function useBackoffPoll(active: boolean, run: () => Promise<void>): void {
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let timer = 0;
    let attempt = 0;
    const step = async () => {
      if (cancelled) return;
      await run();
      if (cancelled) return;
      attempt += 1;
      timer = window.setTimeout(step, BACKOFF[Math.min(attempt, BACKOFF.length - 1)]);
    };
    timer = window.setTimeout(step, BACKOFF[0]);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [active, run]);
}

/**
 * While `active`, call `run` every `intervalMs` — but only while the tab is visible, and once more
 * the moment it becomes visible again. For waiting on something another person does (a friend's
 * first claim reviving this config): a hidden tab polling a server helps nobody.
 */
export function useVisiblePoll(active: boolean, run: () => Promise<void>, intervalMs = 25000): void {
  useEffect(() => {
    if (!active) return;
    const visible = () => document.visibilityState === "visible";
    const id = window.setInterval(() => {
      if (visible()) void run();
    }, intervalMs);
    const onVisibility = () => {
      if (visible()) void run();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active, run, intervalMs]);
}
