import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { ClaimWidget } from "@/components/ClaimWidget";
import { RewardsTeaser } from "@/components/RewardsTeaser";

export default async function HomePage() {
  const locale = await getLocale();
  const t = translator(locale);
  return (
    <>
      <section className="hero">
        <div className="container hero-inner">
          <div>
            <span className="eyebrow">{t("hero.eyebrow")}</span>
            <h1>{t("hero.title")}</h1>
            <p className="lead">{t("hero.sub")}</p>
            <div className="hero-cta">
              <Link href="/status" className="btn btn-primary btn-lg">
                {t("hero.cta")}
              </Link>
              <Link href="/status" className="btn btn-ghost btn-lg">
                {t("hero.ctaStatus")}
              </Link>
            </div>
            <div className="hero-trust">
              <span>✓ {t("trust.noSignup")}</span>
              <span>✓ {t("trust.noEmail")}</span>
              <span>✓ {t("trust.daily")}</span>
              <span>✓ {t("trust.private")}</span>
            </div>
          </div>
          <div className="hero-art" aria-hidden>
            <div className="stack">
              <div className="between">
                <strong style={{ fontSize: 18 }}>GozarX</strong>
                <span className="chip" style={{ background: "rgba(255,255,255,.16)", color: "inherit" }}>
                  {t("trust.daily")}
                </span>
              </div>
              <div className="meter" style={{ background: "rgba(255,255,255,.18)" }}>
                <i style={{ width: "62%", background: "#fff" }} />
              </div>
              <div className="row" style={{ gap: 16, marginTop: 8 }}>
                <div>
                  <div style={{ opacity: 0.8, fontSize: 12 }}>{t("status.usage")}</div>
                  <div className="tnum" style={{ fontSize: 22, fontWeight: 800 }}>380 MB</div>
                </div>
                <div>
                  <div style={{ opacity: 0.8, fontSize: 12 }}>{t("status.dailyLimit")}</div>
                  <div className="tnum" style={{ fontSize: 22, fontWeight: 800 }}>1 GB</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section style={{ paddingBlockStart: 0 }}>
        <div className="container grid-2" style={{ alignItems: "start" }}>
          <div>
            <h2>{t("claim.title")}</h2>
            <p className="lead mt-2">{t("hero.sub")}</p>
          </div>
          <ClaimWidget locale={locale} />
        </div>
      </section>

      <RewardsTeaser locale={locale} />
    </>
  );
}
