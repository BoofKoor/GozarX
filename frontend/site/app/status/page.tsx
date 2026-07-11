import { getLocale } from "@/lib/server";
import { StatusView } from "@/components/StatusView";

export default async function StatusPage() {
  const locale = await getLocale();
  return (
    <section className="sec">
      <StatusView locale={locale} />
    </section>
  );
}
