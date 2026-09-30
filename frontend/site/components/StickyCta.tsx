"use client";

import { useEffect, useState } from "react";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Icon } from "@/components/Icon";

const OTHER_CTAS = ".ft-cta, .land-cta";

// A thumb-reach "get a config" bar for phones, shown only while the claim widget is OFF-screen — it
// never doubles a button the visitor can already see, which is also why it steps aside while the
// footer's (or a landing's closing) call to action is on screen. It takes them back to the widget
// rather than claiming from here, because the location choice lives there. Hidden during a
// cooldown (there is nothing to do yet) and, by CSS, from 940px up, where the hero keeps the widget
// beside the copy.
export function StickyCta({ locale, target }: { locale: Locale; target: string }) {
  const t = translator(locale);
  const { status, loading } = useSite();
  const [offscreen, setOffscreen] = useState(false);
  const [otherCta, setOtherCta] = useState(false);

  useEffect(() => {
    const el = document.querySelector(target);
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setOffscreen(!entry.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, [target]);

  // the page's other calls to action (the footer band, a landing's closing band)
  useEffect(() => {
    const els = document.querySelectorAll(OTHER_CTAS);
    if (!els.length) return;
    const seen = new Set<Element>();
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) seen.add(e.target);
        else seen.delete(e.target);
      }
      setOtherCta(seen.size > 0);
    });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  const hasConfig = !!status?.has_config;
  const show = !loading && offscreen && !otherCta && (hasConfig || (status?.can_claim ?? true));

  function go() {
    const el = document.querySelector<HTMLElement>(target);
    if (!el) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "start", behavior: still ? "auto" : "smooth" });
    // land on the widget's heading, so a screen reader says where the button went
    el.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
  }

  return (
    <div className={`sticky-cta${show ? " show" : ""}`} aria-hidden={!show} inert={!show}>
      <button type="button" className="btn cta" onClick={go}>
        <Icon name="bolt" sw={2.2} />
        {hasConfig ? t("sticky_mine") : t("sticky_get")}
      </button>
    </div>
  );
}
