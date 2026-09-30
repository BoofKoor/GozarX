import type { Metadata } from "next";
import Link from "@/components/Link";
import { type LangParams, localeOf } from "@/lib/server";
import { translator } from "@/lib/copy";
import { fetchSiteCopy } from "@/lib/siteCopy";
import { Icon } from "@/components/Icon";
import "@/styles/pages.css";

export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  const t = translator(locale, (await fetchSiteCopy(locale)).overrides);
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${t("about_title")} — GozarX`,
    description: t("about_lead"),
    alternates: { canonical: "/about" },
  };
}

// About — its own page (C-33). It used to be the contact page's first half under a second URL, so
// the two carried the same heading and the same two paragraphs. Now: what GozarX is for, how it
// stays free, and what it keeps about a visitor. The prose is editable in the panel (site copy,
// "about" group): what funds the service is the operator's to say, so the in-code paragraph only
// states what the product itself shows — no payment step, a trial with a set length and volume.
export default async function AboutPage({ params }: { params: LangParams }) {
  const locale = await localeOf(params);
  const t = translator(locale, (await fetchSiteCopy(locale)).overrides);
  const blocks = [
    { icon: "spark", h: "about_mission_h", body: "about_body" },
    { icon: "gift", h: "about_free_h", body: "about_free_body" },
    { icon: "shield", h: "about_privacy_h", body: "about_privacy_body", more: "/privacy" },
  ] as const;

  return (
    <>
      <div className="container">
        <div className="page-head about-head">
          <span className="eyebrow">
            <Icon name="info" sw={2.2} />
            {t("about_eyebrow")}
          </span>
          <h1>{t("about_title")}</h1>
          <p className="about-lead">{t("about_lead")}</p>
        </div>
      </div>
      <section className="sec" style={{ paddingBlockStart: 20 }}>
        <div className="container">
          <div className="about-grid">
            {blocks.map((b) => (
              <article key={b.h} className="card about-card">
                <span className="htile" aria-hidden>
                  <Icon name={b.icon} sw={2} />
                </span>
                <h2>{t(b.h)}</h2>
                <p>{t(b.body)}</p>
                {"more" in b && (
                  <Link className="about-more" href={b.more}>
                    {t("about_privacy_link")}
                    <Icon name="arrow" sw={2.2} cls="ic-dir" />
                  </Link>
                )}
              </article>
            ))}
          </div>
          <div className="deflect about-deflect">
            <h2>{t("about_deflect")}</h2>
            <Link href="/faq">
              <Icon name="help" sw={2} />
              {t("nav_faq")}
              <Icon name="arrow" sw={2.2} cls="ic-dir" />
            </Link>
            <Link href="/guides">
              <Icon name="book" sw={2} />
              {t("ft_guides")}
              <Icon name="arrow" sw={2.2} cls="ic-dir" />
            </Link>
            <Link href="/contact">
              <Icon name="mail" sw={2} />
              {t("contact.title")}
              <Icon name="arrow" sw={2.2} cls="ic-dir" />
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
