import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { GUIDE_LABELS, guideList } from "@/lib/content";
import { Icon } from "@/components/Icon";
import { BrandIcon } from "@/components/BrandIcon";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  // Self-referencing canonical (relative — metadataBase is set in the root layout).
  return {
    title: `${GUIDE_LABELS[locale].title} — GozarX`,
    description: GUIDE_LABELS[locale].sub,
    alternates: { canonical: "/guides" },
  };
}

// Guides index — pick your OS. Each card carries the platform's official brand mark in an accent
// tile, the Happ app pill, and a circular "open" affordance. All guides now target Happ.
export default async function GuidesPage() {
  const locale = await getLocale();
  const labels = GUIDE_LABELS[locale];
  const guides = guideList(locale);
  return (
    <>
      <div className="container">
        <div className="page-head c">
          <span className="eyebrow">
            <Icon name="plug" sw={2} />
            {labels.eyebrow}
          </span>
          <h1>{labels.title}</h1>
          <p>{labels.sub}</p>
        </div>
      </div>
      <section className="sec guides-sec">
        <div className="container" style={{ maxWidth: 900 }}>
          <div className="gwrap">
            {guides.map((g) => (
              <Link
                key={g.platform}
                href={`/guides/${g.platform}`}
                className="gcard"
                style={{ ["--acc" as string]: g.acc }}
              >
                <span className="gos">
                  <span className="glow" aria-hidden />
                  <BrandIcon name={g.os} />
                </span>
                <span className="gcard-id">
                  <span className="gtop">
                    <b>{g.name}</b>
                    <span className="gtag">{labels.easy}</span>
                  </span>
                  <span className="gsub">
                    <span className="gpill">
                      <img src="/icons/happ.webp" alt="" width={17} height={17} />
                      {g.app}
                    </span>
                    <span className="gtime">
                      <Icon name="clock" sw={2} />
                      {labels.time}
                    </span>
                  </span>
                </span>
                <span className="gchevw" aria-hidden>
                  <svg className="gchev" viewBox="0 0 24 24" width={20} height={20} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                    <path d="m14 6-6 6 6 6" />
                  </svg>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
