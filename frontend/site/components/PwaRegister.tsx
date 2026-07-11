"use client";

import { useEffect } from "react";

// Registers the service worker (offline shell + Web Push handling). Best-effort and silent — a failed
// registration (e.g. unsupported browser, http dev without SW) never breaks the page.
export function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const onLoad = () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    };
    if (document.readyState === "complete") onLoad();
    else window.addEventListener("load", onLoad, { once: true });
  }, []);
  return null;
}
