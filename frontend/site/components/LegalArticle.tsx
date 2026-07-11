import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { LEGAL_IMPORTANT, LEGAL_UPDATED, type LegalSection } from "@/lib/content";

// Shared renderer for the two legal pages (privacy / terms). An `important` section renders as an
// emphasised callout (the Phase-5 "device identity" note). `other` links to the sibling legal page.
export function LegalArticle({
  locale,
  title,
  sections,
  other,
}: {
  locale: Locale;
  title: string;
  sections: LegalSection[];
  other: { href: string; label: string };
}) {
  return (
    <section>
      <div className="container" style={{ maxWidth: 720 }}>
        <h1>{title}</h1>
        <p className="hint mt-2">{LEGAL_UPDATED[locale]}</p>

        <div className="stack mt-6">
          {sections.map((s, i) =>
            s.important ? (
              <div key={i} className="card card-pad" style={{ borderColor: "var(--primary)", background: "var(--brand-tint)" }}>
                <h2 style={{ fontSize: 20 }}>{s.h}</h2>
                <p className="mt-2" style={{ color: "var(--text)" }}>
                  <strong style={{ color: "var(--primary)" }}>{LEGAL_IMPORTANT[locale]} </strong>
                  {s.body}
                </p>
              </div>
            ) : (
              <div key={i}>
                <h2 style={{ fontSize: 20 }}>{s.h}</h2>
                <p className="mt-2">{s.body}</p>
              </div>
            ),
          )}
        </div>

        <p className="hint mt-6">
          <Link href={other.href} style={{ color: "var(--link)" }}>
            {other.label}
          </Link>
        </p>
      </div>
    </section>
  );
}
