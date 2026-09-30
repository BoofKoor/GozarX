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
        {/* the page's title, so it is an h1 — it was a chip with no heading on the page at all */}
        <h1 className="chip chip-warning offline-h">{t("offline.title")}</h1>
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
