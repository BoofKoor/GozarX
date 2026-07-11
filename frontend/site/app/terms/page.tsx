import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { LegalArticle } from "@/components/LegalArticle";
import { LEGAL_TITLE, TERMS } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${LEGAL_TITLE[locale].terms} — GozarX` };
}

export default async function TermsPage() {
  const locale = await getLocale();
  return (
    <LegalArticle
      locale={locale}
      title={LEGAL_TITLE[locale].terms}
      sections={TERMS[locale]}
      other={{ href: "/privacy", label: LEGAL_TITLE[locale].privacy }}
    />
  );
}
