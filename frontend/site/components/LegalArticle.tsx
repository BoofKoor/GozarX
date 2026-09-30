import Link from "next/link";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { LEGAL_IMPORTANT, LEGAL_TITLE, LEGAL_TOC, legalUpdated, type LegalSection } from "@/lib/content";
import { Icon } from "@/components/Icon";

// The two legal pages, in the design's `vLegal` shape (C-34): a crumb, the terms/privacy switch, the
// title with its last-updated date, then a numbered table of contents (sticky beside the text from
// 900px) and the numbered sections it links to. It was a plain column with no contents, no numbers
// and a fixed «تیر ۱۴۰۴» that was the mockup's placeholder. An `important` section is the callout.
export function LegalArticle({
  locale,
  kind,
  sections,
}: {
  locale: Locale;
  kind: "terms" | "privacy";
  sections: LegalSection[];
}) {
  const t = translator(locale);
  const titles = LEGAL_TITLE[locale];
  const n = (i: number) => faDigits(i + 1, locale);
  return (
    <section className="sec legal-page">
      <div className="container">
        <nav className="crumbs" aria-label={t("crumbs")}>
          <Link href="/">{t("land_home")}</Link>
          <Icon name="chevr" sw={2.2} cls="ic-dir crumb-sep" />
          <span aria-current="page">{titles[kind]}</span>
        </nav>
        <nav className="legal-switch" aria-label={t("ftc_legal")}>
          {(["terms", "privacy"] as const).map((k) => (
            <Link key={k} href={`/${k}`} aria-current={k === kind ? "page" : undefined}>
              {titles[k]}
            </Link>
          ))}
        </nav>
        <h1>{titles[kind]}</h1>
        <p className="updated">{legalUpdated(locale)}</p>

        <div className="doc">
          <nav className="toc" aria-labelledby="toc-label">
            <p id="toc-label" className="toc-h">
              {LEGAL_TOC[locale]}
            </p>
            <ol>
              {sections.map((s, i) => (
                <li key={i}>
                  <a href={`#lg-${i + 1}`}>
                    {n(i)}. {s.h}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
          <div className="legal-body">
            {sections.map((s, i) => (
              <section key={i} aria-labelledby={`lg-${i + 1}`}>
                <h2 id={`lg-${i + 1}`}>
                  <span className="n">{n(i)}.</span> {s.h}
                </h2>
                {s.important ? (
                  <div className="privacy-note">
                    <Icon name="shield" sw={2} />
                    <p>
                      <b>{LEGAL_IMPORTANT[locale]}</b> {s.body}
                    </p>
                  </div>
                ) : (
                  <p>{s.body}</p>
                )}
              </section>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
