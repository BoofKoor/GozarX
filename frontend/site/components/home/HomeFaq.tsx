"use client";

import Link from "next/link";
import { useState } from "react";
import { type CopyOverrides, type Locale, translator } from "@/lib/i18n";
import type { FaqItem } from "@/lib/content";
import { AccItem } from "@/components/Accordion";

// FAQ teaser — the design's `.faqwrap` of `.acc` accordions (first open), one `AccItem` each. The
// questions are the first five of the panel's FAQ, in the panel's order (C-36) — read by the page on
// the server, with the same in-code fallback as /faq, so reordering in the panel is how an operator
// chooses what the home page asks. They used to be five strings of their own that no edit reached.
export function HomeFaq({
  locale,
  copy,
  items,
}: {
  locale: Locale;
  copy?: CopyOverrides;
  items: FaqItem[];
}) {
  const t = translator(locale, copy);
  const [open, setOpen] = useState(0);
  if (items.length === 0) return null;

  return (
    <section className="sec" id="faq" style={{ background: "var(--sunken)" }}>
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("faq_eyebrow")}</span>
          <h2 className="sec-title">{t("faq_title")}</h2>
        </div>
        <div className="faqwrap reveal">
          {items.map((item, i) => (
            <AccItem
              key={item.q}
              question={item.q}
              open={open === i}
              onToggle={() => setOpen((cur) => (cur === i ? -1 : i))}
              onReveal={() => setOpen(i)}
            >
              {item.a}
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
