import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { LegalArticle } from "@/components/LegalArticle";
import { LEGAL_TITLE, PRIVACY } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${LEGAL_TITLE[locale].privacy} — GozarX` };
}

export default async function PrivacyPage() {
  const locale = await getLocale();
  return (
    <LegalArticle
      locale={locale}
      title={LEGAL_TITLE[locale].privacy}
      sections={PRIVACY[locale]}
      other={{ href: "/terms", label: LEGAL_TITLE[locale].terms }}
    />
  );
}
