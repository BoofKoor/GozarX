import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { ContactForm } from "@/components/ContactForm";

export default async function ContactPage() {
  const locale = await getLocale();
  const t = translator(locale);
  return (
    <section>
      <div className="container" style={{ maxWidth: 640 }}>
        <h1>{t("contact.title")}</h1>
        <p className="lead mt-2">{t("contact.sub")}</p>
        <ContactForm locale={locale} />
      </div>
    </section>
  );
}
