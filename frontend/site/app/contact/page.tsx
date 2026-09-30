import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator, type Locale } from "@/lib/i18n";
import { Icon } from "@/components/Icon";
import { ContactForm } from "@/components/ContactForm";

// Meta description is page-local (the i18n chrome map holds UI labels, not SEO copy); the title
// reuses the existing "contact.title" chrome string. Self-referencing canonical per the homepage
// idiom — one URL serves both locales by cookie, so no alternates.languages.
const META_DESC: Record<Locale, string> = {
  fa: "سوال یا مشکلی داری؟ از طریق فرم تماس سایت به تیم پشتیبانی GozarX پیام بده — بدون ایمیل و بدون ثبت‌نام. پاسخ خیلی از سوال‌ها هم در سوالات متداول و راهنماها هست.",
  en: "Questions or issues? Message the GozarX support team via the on-site contact form — no email or signup needed. Many answers are already in the FAQ and guides.",
};

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  const t = translator(locale);
  return {
    title: `${t("contact.title")} — GozarX`,
    description: META_DESC[locale],
    alternates: { canonical: "/contact" },
  };
}

// Contact page — the design's `vContact` two-column layout: a short "write to us" blurb that
// deflects to the FAQ and the guides on one side, the form on the other. It used to open with the
// About page's heading and both of its paragraphs (C-33); /about is its own page now. No
// email/social — the form is the only support channel.
export default async function ContactPage() {
  const locale = await getLocale();
  const t = translator(locale);
  return (
    <>
      <div className="container">
        <div className="page-head">
          <span className="eyebrow">
            <Icon name="mail" sw={2.2} />
            {t("v_contact")}
          </span>
          <h1>{t("contact.title")}</h1>
        </div>
      </div>
      <section className="sec" style={{ paddingBlockStart: 20 }}>
        <div className="container">
          <div className="two">
            <div className="mission">
              <p className="lead">{t("contact.sub")}</p>
              <p>
                {t("contact.about")} <Link href="/about">{t("about_title")}</Link>
              </p>
              <div className="deflect">
                <h2>{t("about_deflect")}</h2>
                <Link href="/faq">
                  <Icon name="help" sw={2} />
                  {t("nav_faq")}
                  <Icon name="arrow" sw={2.2} cls="ic-dir" />
                </Link>
                <Link href="/guides">
                  <Icon name="book" sw={2} />
                  {t("ft_guides")}
                  <Icon name="arrow" sw={2.2} cls="ic-dir" />
                </Link>
              </div>
            </div>
            <ContactForm locale={locale} />
          </div>
        </div>
      </section>
    </>
  );
}
