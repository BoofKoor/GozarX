"use client";

import Link from "next/link";
import { useState } from "react";
import { type Locale, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

// FAQ teaser — the design's `.faqwrap` of `.acc` accordions (first open). Toggles `data-open`
// exactly like the artifact; the CSS drives the body reveal + chevron rotation.
const QA = ["faq1", "faq2", "faq3", "faq4", "faq5"] as const;

export function HomeFaq({ locale }: { locale: Locale }) {
  const t = translator(locale);
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
            <div className="acc" key={q} data-open={open === i ? "true" : "false"}>
              <button
                className="acc-head"
                aria-expanded={open === i}
                onClick={() => setOpen((cur) => (cur === i ? -1 : i))}
              >
                <span>{t(`${q}_q`)}</span>
                <Icon name="chev" sw={2} />
              </button>
              <div className="acc-body">{t(`${q}_a`)}</div>
            </div>
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
