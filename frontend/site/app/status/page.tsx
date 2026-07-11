import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { StatusView } from "@/components/StatusView";

export default async function StatusPage() {
  const locale = await getLocale();
  const t = translator(locale);
  return (
    <section>
      <div className="container">
        <h1>{t("status.title")}</h1>
        <StatusView locale={locale} />
      </div>
    </section>
  );
}
