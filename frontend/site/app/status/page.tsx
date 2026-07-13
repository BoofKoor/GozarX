import type { Metadata } from "next";
import { getLocale } from "@/lib/server";
import { StatusView } from "@/components/StatusView";

// Personalized, device-specific account view — keep it out of the index (also disallowed in robots).
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function StatusPage() {
  const locale = await getLocale();
  return (
    <section className="sec status-sec">
      <StatusView locale={locale} />
    </section>
  );
}
