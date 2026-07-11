import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";

export default async function NotFound() {
  const locale = await getLocale();
  const t = translator(locale);
  return (
    <section>
      <div className="container center stack">
        <h1 style={{ fontSize: 64 }}>404</h1>
        <p className="lead" style={{ marginInline: "auto" }}>
          {t("notfound.title")}
        </p>
        <div className="center mt-4">
          <Link href="/" className="btn btn-primary btn-lg">
            {t("notfound.home")}
          </Link>
        </div>
      </div>
    </section>
  );
}
