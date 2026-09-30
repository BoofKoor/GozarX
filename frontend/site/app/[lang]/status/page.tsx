import type { Metadata } from "next";
import { type LangParams, localeOf } from "@/lib/server";
import { translator } from "@/lib/copy";
import { StatusView } from "@/components/StatusView";
import "@/styles/status.css";

// Personalized, device-specific view — keep it out of the index (also disallowed in robots). It
// still needs its own title: without one the tab and the history list read as the home page.
export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  return {
    title: `${translator(locale)("title")} — GozarX`,
    robots: { index: false, follow: false },
  };
}

export default async function StatusPage({ params }: { params: LangParams }) {
  const locale = await localeOf(params);
  return (
    <section className="sec status-sec">
      <StatusView locale={locale} />
    </section>
  );
}
