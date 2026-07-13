import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { RetryButton } from "@/components/RetryButton";

// PWA offline fallback — not a real content page; keep it out of the index (also disallowed in robots).
export const metadata: Metadata = { robots: { index: false, follow: false } };

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
