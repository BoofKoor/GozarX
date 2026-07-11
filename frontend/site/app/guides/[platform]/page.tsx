import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale } from "@/lib/server";
import { GUIDE_LABELS, SAMPLE_CONFIG, guideFor } from "@/lib/content";
import { CopyField } from "@/components/CopyField";

function heading(localeFa: boolean, name: string, app: string): string {
  return localeFa ? `اتصال ${name} با ${app}` : `${name} — ${app}`;
}

export async function generateMetadata({ params }: { params: Promise<{ platform: string }> }): Promise<Metadata> {
  const { platform } = await params;
  const locale = await getLocale();
  const g = guideFor(locale, platform);
  if (!g) return { title: `GozarX — ${GUIDE_LABELS[locale].title}` };
  return { title: `${heading(locale === "fa", g.name, g.app)} — GozarX` };
}

export default async function GuidePage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  const locale = await getLocale();
  const g = guideFor(locale, platform);
  if (!g) notFound();
  const labels = GUIDE_LABELS[locale];

  return (
    <section>
      <div className="container" style={{ maxWidth: 720 }}>
        <p className="hint">
          <Link href="/guides" style={{ color: "var(--link)" }}>
            ← {labels.backToGuides}
          </Link>
        </p>
        <h1 className="mt-2">{heading(locale === "fa", g.name, g.app)}</h1>
        <div className="row mt-2" style={{ flexWrap: "wrap", gap: 8 }}>
          <span className="chip">{g.app}</span>
          <span className="chip chip-success">{labels.easy}</span>
          <span className="chip chip-muted">{labels.time}</span>
        </div>

        <h2 className="mt-6" style={{ fontSize: 22 }}>
          {labels.steps}
        </h2>
        <ol className="stack mt-4" style={{ listStyle: "none" }}>
          {g.steps.map((s, i) => (
            <li key={i} className="card card-pad">
              <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
                <span
                  aria-hidden
                  className="tnum"
                  style={{
                    flex: "0 0 auto",
                    width: 30,
                    height: 30,
                    borderRadius: "var(--r-pill)",
                    background: "var(--brand-tint)",
                    color: "var(--brand-tint-ink)",
                    display: "grid",
                    placeItems: "center",
                    fontWeight: 800,
                  }}
                >
                  {i + 1}
                </span>
                <div style={{ flex: 1 }}>
                  <strong>{s.t}</strong>
                  <p className="mt-2">{s.d}</p>
                  {s.copy && <CopyField value={SAMPLE_CONFIG} copyLabel={labels.copy} copiedLabel={labels.copied} />}
                </div>
              </div>
            </li>
          ))}
        </ol>

        <h2 className="mt-6" style={{ fontSize: 22 }}>
          {labels.trouble}
        </h2>
        <div className="stack mt-4">
          {g.trouble.map((tr, i) => (
            <details key={i} className="card card-pad">
              <summary style={{ fontWeight: 700, cursor: "pointer" }}>{tr.q}</summary>
              <p className="mt-2">{tr.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
