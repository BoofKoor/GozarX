"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

// Progressive-enhancement scroll reveal. Content ships visible (no-JS safe); on mount we add
// `reveal-js` to #app — which arms the CSS fade-up — then observe every `.reveal` and add `.in`
// as it scrolls into view. Elements already on screen reveal immediately (matches the design's
// on-load entrance). Re-runs on route change so a client-navigated page's `.reveal` elements get
// observed too. A short safety timer reveals anything still hidden, so a stalled observer can
// never leave content invisible. Honors reduced-motion via the CSS media query.
export function RevealObserver() {
  const pathname = usePathname();
  useEffect(() => {
    const app = document.getElementById("app");
    if (!app || typeof IntersectionObserver === "undefined") return;
    const els = Array.from(app.querySelectorAll<HTMLElement>(".reveal"));
    if (!els.length) return;
    app.classList.add("reveal-js");
    const io = new IntersectionObserver(
      (entries, obs) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            obs.unobserve(e.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    els.forEach((el) => io.observe(el));
    // Safety net: never leave content stuck hidden if the observer stalls for any reason.
    const safety = setTimeout(() => els.forEach((el) => el.classList.add("in")), 4000);
    return () => {
      io.disconnect();
      clearTimeout(safety);
    };
  }, [pathname]);
  return null;
}
