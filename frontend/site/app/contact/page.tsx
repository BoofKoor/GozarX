import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";
import { ContactForm } from "@/components/ContactForm";

// Contact page — faithful reproduction of the design's `vContact`: page head + a two-column layout
// with the mission/deflect blurb (deflecting to FAQ + guides) on one side and the contact form on
// the other. No email/social — the form is the only support channel.
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
          <h1>{t("about_title")}</h1>
        </div>
      </div>
      <section className="sec" style={{ paddingBlockStart: 20 }}>
        <div className="container">
          <div className="two">
            <div className="mission">
              <p className="lead">{t("about_lead")}</p>
              <p>{t("about_body")}</p>
              <div className="deflect">
                <h4>{t("about_deflect")}</h4>
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
