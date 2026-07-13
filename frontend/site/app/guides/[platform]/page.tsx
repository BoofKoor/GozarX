import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale } from "@/lib/server";
import { GUIDE_LABELS, guideFor } from "@/lib/content";
import { Icon } from "@/components/Icon";
import { BrandIcon } from "@/components/BrandIcon";

// "اتصال ویندوز با Happ" — strip the "(iOS)"/"(macOS)" parenthetical so the heading stays tight.
function heading(labels: { connect: string }, name: string): string {
  return labels.connect.replace("{name}", name.replace(/\s*\(.*\)/, ""));
}

export async function generateMetadata({ params }: { params: Promise<{ platform: string }> }): Promise<Metadata> {
  const { platform } = await params;
  const locale = await getLocale();
  const g = guideFor(locale, platform);
  if (!g) return { title: `GozarX — ${GUIDE_LABELS[locale].title}` };
  return { title: `${heading(GUIDE_LABELS[locale], g.name)} — GozarX` };
}

export default async function GuidePage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  const locale = await getLocale();
  const g = guideFor(locale, platform);
  if (!g) notFound();
  const labels = GUIDE_LABELS[locale];
  const acc = { ["--acc" as string]: g.acc };

  return (
    <section className="guide-page">
      <div className="container" style={{ maxWidth: 720 }}>
        <p className="hint">
          <Link href="/guides" className="gback">
            {locale === "fa" ? "→" : "←"} {labels.backToGuides}
          </Link>
        </p>

        <div className="ghero">
          <span className="gos gbig" style={acc}>
            <span className="glow" aria-hidden />
            <BrandIcon name={g.os} />
          </span>
          <div className="ghero-txt">
            <h1>{heading(labels, g.name)}</h1>
            <div className="grow">
              <span className="chip happ">
                <img src="/icons/happ.webp" alt="" className="chip-app" width={15} height={15} />
                {g.app}
              </span>
              <span className="chip chip-success">{labels.easy}</span>
              <span className="chip chip-muted">
                <Icon name="clock" sw={2} />
                {labels.time}
              </span>
            </div>
          </div>
        </div>

        <h2 className="gsteps-h">{labels.steps}</h2>
        <div className="tl">
          {g.steps.map((s, i) => (
            <div className={`tstep${i === g.steps.length - 1 ? " last" : ""}`} key={i}>
              <span className="tbadge">{i + 1}</span>
              <div className="tcard">
                <strong>{s.t}</strong>
                <p className="mt-2">{s.d}</p>
                {i === 0 && (
                  <a
                    className="dlbtn"
                    href={g.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={acc}
                    aria-label={`${g.dl.top} ${g.dl.bottom}`}
                  >
                    <span className="store">
                      <BrandIcon name={g.store} />
                    </span>
                    <span className="dlt">
                      <small>{g.dl.top}</small>
                      <b>{g.dl.bottom}</b>
                    </span>
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>

        <h2 className="gsteps-h">{labels.trouble}</h2>
        <div className="stack">
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
