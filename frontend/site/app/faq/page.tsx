import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { FaqList } from "@/components/FaqList";
import { FAQ_LABELS } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${FAQ_LABELS[locale].title} — GozarX`, description: FAQ_LABELS[locale].sub };
}

export default async function FaqPage() {
  const locale = await getLocale();
  const labels = FAQ_LABELS[locale];
  return (
    <section>
      <div className="container" style={{ maxWidth: 720 }}>
        <h1>{labels.title}</h1>
        <p className="lead mt-2">{labels.sub}</p>
        <FaqList locale={locale} />
      </div>
    </section>
  );
}
