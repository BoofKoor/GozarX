import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { GUIDES, GUIDE_LABELS } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${GUIDE_LABELS[locale].title} — GozarX`, description: GUIDE_LABELS[locale].sub };
}

export default async function GuidesPage() {
  const locale = await getLocale();
  const labels = GUIDE_LABELS[locale];
  return (
    <section>
      <div className="container" style={{ maxWidth: 900 }}>
        <h1>{labels.title}</h1>
        <p className="lead mt-2">{labels.sub}</p>

        <div className="grid-2 mt-6">
          {GUIDES[locale].map((g) => (
            <Link key={g.platform} href={`/guides/${g.platform}`} className="card card-pad" style={{ display: "block", color: "var(--text)" }}>
              <div className="between">
                <h2 style={{ fontSize: 20 }}>{g.name}</h2>
                <span className="chip chip-success">{labels.easy}</span>
              </div>
              <p className="hint mt-2">
                {labels.apps} {g.app} · {labels.time}
              </p>
              <span className="btn btn-ghost btn-block mt-4">{labels.view}</span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
