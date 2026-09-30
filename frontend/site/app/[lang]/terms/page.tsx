import type { Metadata } from "next";
import { type LangParams, localeOf } from "@/lib/server";
import type { Locale } from "@/lib/i18n";
import { LegalArticle } from "@/components/LegalArticle";
import { LEGAL_TITLE, TERMS } from "@/lib/content";
import "@/styles/pages.css";

// Meta description summarising the terms (mirrors the TERMS sections: free daily trial config,
// provided as-is, fair use required, abuse voids access). Kept under ~160 chars for SERPs.
const META_DESC: Record<Locale, string> = {
  fa: "قوانین استفاده از GozarX: سرویس رایگان کانفیگ آزمایشی روزانه که «همان‌طور که هست» ارائه می‌شود؛ استفادهٔ منصفانه شرط است و سوءاستفاده دسترسی را لغو می‌کند.",
  en: "GozarX terms of use: a free daily trial-config service provided as is; fair use is required and abuse — multiple accounts or bots — voids your access.",
};

export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${LEGAL_TITLE[locale].terms} — GozarX`,
    description: META_DESC[locale],
    alternates: { canonical: "/terms" },
  };
}

export default async function TermsPage({ params }: { params: LangParams }) {
  const locale = await localeOf(params);
  return (
    <LegalArticle locale={locale} kind="terms" sections={TERMS[locale]} />
  );
}
