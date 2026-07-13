import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { FaqList } from "@/components/FaqList";
import { Icon } from "@/components/Icon";
import { translator } from "@/lib/i18n";
import { FAQ_LABELS } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${FAQ_LABELS[locale].title} — GozarX`,
    description: FAQ_LABELS[locale].sub,
    alternates: { canonical: "/faq" },
  };
}

export default async function FaqPage() {
  const locale = await getLocale();
  const t = translator(locale);
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
          <p>{labels.sub}</p>
        </div>
      </div>
      <section className="sec">
        <div className="container narrow">
          <FaqList locale={locale} />
        </div>
      </section>
    </>
  );
}
