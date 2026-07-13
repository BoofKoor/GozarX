import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import type { Locale } from "@/lib/i18n";
import { LegalArticle } from "@/components/LegalArticle";
import { LEGAL_TITLE, TERMS } from "@/lib/content";

// Meta description summarising the terms (mirrors the TERMS sections: free daily trial config,
// provided as-is, fair use required, abuse voids access). Kept under ~160 chars for SERPs.
const META_DESC: Record<Locale, string> = {
  fa: "قوانین استفاده از GozarX: سرویس رایگان کانفیگ آزمایشی روزانه که «همان‌طور که هست» ارائه می‌شود؛ استفادهٔ منصفانه شرط است و سوءاستفاده دسترسی را لغو می‌کند.",
  en: "GozarX terms of use: a free daily trial-config service provided as is; fair use is required and abuse — multiple accounts or bots — voids your access.",
};

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${LEGAL_TITLE[locale].terms} — GozarX`,
    description: META_DESC[locale],
    alternates: { canonical: "/terms" },
  };
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
