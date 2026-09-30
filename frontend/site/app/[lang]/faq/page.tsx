import type { Metadata } from "next";
import { type LangParams, localeOf } from "@/lib/server";
import { FaqList } from "@/components/FaqList";
import { Icon } from "@/components/Icon";
import { translator } from "@/lib/copy";
import { FAQ_LABELS } from "@/lib/content";
import { fetchFaqItems } from "@/lib/faq";
import { fetchSiteCopy } from "@/lib/siteCopy";
import "@/styles/pages.css";

export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${FAQ_LABELS[locale].title} — GozarX`,
    description: FAQ_LABELS[locale].sub,
    alternates: { canonical: "/faq" },
  };
}

export default async function FaqPage({ params }: { params: LangParams }) {
  const locale = await localeOf(params);
  // Panel-managed rows, falling back to the in-code list — see lib/faq.ts.
  const items = await fetchFaqItems(locale);
  // `faq_sub` is a panel-editable key that no page read — its edits went nowhere. This is its page.
  const t = translator(locale, (await fetchSiteCopy(locale)).overrides);
  const labels = FAQ_LABELS[locale];
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
          <FaqList locale={locale} items={items} />
        </div>
      </section>
    </>
  );
}
