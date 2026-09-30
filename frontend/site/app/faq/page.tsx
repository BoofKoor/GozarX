import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { FaqList } from "@/components/FaqList";
import { Icon } from "@/components/Icon";
import { translator } from "@/lib/i18n";
import { FAQ_LABELS } from "@/lib/content";
import { fetchFaqItems } from "@/lib/faq";
import { fetchSiteCopy } from "@/lib/siteCopy";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${FAQ_LABELS[locale].title} — GozarX`,
    description: FAQ_LABELS[locale].sub,
    alternates: { canonical: "/faq" },
  };
}

export default async function FaqPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const locale = await getLocale();
  // Panel-managed rows, falling back to the in-code list — see lib/faq.ts.
  const items = await fetchFaqItems(locale);
  // `faq_sub` is a panel-editable key that no page read — its edits went nowhere. This is its page.
  const t = translator(locale, (await fetchSiteCopy(locale)).overrides);
  const labels = FAQ_LABELS[locale];
  // the 404 page's search box lands here with the words already typed
  const q = (await searchParams).q;
  return (
    <>
      <div className="container">
        <div className="page-head c">
          <span className="eyebrow">
            <Icon name="help" sw={2.2} />
            {t("nav_faq")}
          </span>
          <h1>{labels.title}</h1>
          <p>{t("faq_sub")}</p>
        </div>
      </div>
      <section className="sec">
        <div className="container narrow">
          <FaqList locale={locale} items={items} initialQuery={typeof q === "string" ? q.slice(0, 80) : ""} />
        </div>
      </section>
    </>
  );
}
