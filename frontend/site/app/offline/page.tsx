import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { RetryButton } from "@/components/RetryButton";

export default async function OfflinePage() {
  const locale = await getLocale();
  const t = translator(locale);
  return (
    <section>
      <div className="container center stack">
        <span className="chip chip-warning" style={{ fontSize: 15 }}>
          {t("offline.title")}
        </span>
        <p className="lead" style={{ marginInline: "auto" }}>
          {t("offline.sub")}
        </p>
        <div className="center mt-4">
          <RetryButton label={t("offline.retry")} />
        </div>
      </div>
    </section>
  );
}
