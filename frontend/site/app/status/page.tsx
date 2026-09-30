import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { StatusView } from "@/components/StatusView";

// Personalized, device-specific view — keep it out of the index (also disallowed in robots). It
// still needs its own title: without one the tab and the history list read as the home page.
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return {
    title: `${translator(locale)("title")} — GozarX`,
    robots: { index: false, follow: false },
  };
}

export default async function StatusPage() {
  const locale = await getLocale();
  return (
    <section className="sec status-sec">
      <StatusView locale={locale} />
    </section>
  );
}
