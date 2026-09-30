import type { Metadata } from "next";
import { type LangParams, localeOf } from "@/lib/server";
import type { Locale } from "@/lib/i18n";
import { LegalArticle } from "@/components/LegalArticle";
import { LEGAL_TITLE, PRIVACY } from "@/lib/content";
import "@/styles/pages.css";

// Meta description summarising the policy (mirrors the PRIVACY sections: nothing personal stored,
// identity is a light on-browser token, essential cookies only). Kept under ~160 chars for SERPs.
const META_DESC: Record<Locale, string> = {
  fa: "سیاست حریم خصوصی GozarX: بدون ثبت‌نام و بدون ذخیرهٔ نام، ایمیل یا شماره؛ هویتت فقط یک شناسهٔ سبک روی همین مرورگر است و تنها از کوکی‌های ضروری استفاده می‌کنیم.",
  en: "GozarX privacy policy: no signup and no name, email or phone stored; your identity is just a light token on this browser and we only use essential cookies.",
};

export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${LEGAL_TITLE[locale].privacy} — GozarX`,
    description: META_DESC[locale],
    alternates: { canonical: "/privacy" },
  };
}

export default async function PrivacyPage({ params }: { params: LangParams }) {
  const locale = await localeOf(params);
  return (
    <LegalArticle locale={locale} kind="privacy" sections={PRIVACY[locale]} />
  );
}
