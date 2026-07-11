import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { ABOUT } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${ABOUT[locale].title} — GozarX`, description: ABOUT[locale].lead };
}

export default async function AboutPage() {
  const locale = await getLocale();
  const t = translator(locale);
  const a = ABOUT[locale];
  return (
    <section>
      <div className="container" style={{ maxWidth: 680 }}>
        <h1>{a.title}</h1>
        <p className="lead mt-2">{a.lead}</p>
        <p className="mt-4">{a.body}</p>

        <div className="card card-pad mt-6">
          <h4 style={{ color: "var(--faint)", fontSize: 14, marginBottom: 12 }}>{a.deflect}</h4>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <Link href="/faq" className="btn btn-ghost">
              {t("nav.faq")}
            </Link>
            <Link href="/guides" className="btn btn-ghost">
              {t("nav.guides")}
            </Link>
            <Link href="/contact" className="btn btn-ghost">
              {t("nav.contact")}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
