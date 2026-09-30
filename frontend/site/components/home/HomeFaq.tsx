"use client";

import Link from "next/link";
import { useState } from "react";
import { type CopyOverrides, type Locale, translator } from "@/lib/i18n";
import { AccItem } from "@/components/Accordion";

// FAQ teaser — the design's `.faqwrap` of `.acc` accordions (first open), one `AccItem` each.
const QA = ["faq1", "faq2", "faq3", "faq4", "faq5"] as const;

export function HomeFaq({ locale, copy }: { locale: Locale; copy?: CopyOverrides }) {
  const t = translator(locale, copy);
  const [open, setOpen] = useState(0);

  return (
    <section className="sec" id="faq" style={{ background: "var(--sunken)" }}>
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("faq_eyebrow")}</span>
          <h2 className="sec-title">{t("faq_title")}</h2>
        </div>
        <div className="faqwrap reveal">
          {QA.map((q, i) => (
            <AccItem
              key={q}
              question={t(`${q}_q`)}
              open={open === i}
              onToggle={() => setOpen((cur) => (cur === i ? -1 : i))}
              onReveal={() => setOpen(i)}
            >
              {t(`${q}_a`)}
            </AccItem>
          ))}
        </div>
        <div className="center-more reveal">
          <Link className="link-more" href="/faq">
            {t("faq_all")}
          </Link>
        </div>
      </div>
    </section>
  );
}
