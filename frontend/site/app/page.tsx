import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { type Locale, faDigits, fill, translator } from "@/lib/i18n";
import { fetchSiteCopy } from "@/lib/siteCopy";
import { fetchFeaturedArticles } from "@/lib/landing";
import { fetchPublicConfig, fetchPublicStats } from "@/lib/publicData";

// Self-referencing canonical for the homepage. Set here (not in the root layout) so it applies only
// to `/` — a layout-level canonical would be inherited by every sub-page and wrongly mark them all
// as duplicates of the home page.
export const metadata: Metadata = { alternates: { canonical: "/" } };
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { HomeLocations } from "@/components/home/HomeLocations";
import { HomeMissions } from "@/components/home/HomeMissions";
import { HomeApps } from "@/components/home/HomeApps";
import { HomeStats } from "@/components/home/HomeStats";
import { HomeFaq } from "@/components/home/HomeFaq";
import { StickyCta } from "@/components/StickyCta";

// Homepage — faithful reproduction of docs/website/design/phase-2-homepage.html. Section order:
// hero (copy + live claim widget) → how it works → locations → more volume → apps → stats band →
// FAQ → trust band. Interactive/live sections (widget, locations, apps, FAQ) are client islands;
// the rest is static marketing rendered server-side. No economic numbers are hardcoded.
export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const locale = await getLocale();
  // `?loc=<remark>` — a location picked on /locations or in the flag strip, pre-selected in the
  // widget. It used to land on "#hero" with the popular location selected instead of the one tapped.
  const locParam = (await searchParams).loc;
  const preselect = typeof locParam === "string" && locParam.trim() ? locParam.trim() : undefined;
  // Four independent server reads, fetched together rather than one after another:
  //  • editable hero copy from the admin Texts panel (site_hero_title/sub), with the in-code copy as
  //    the fallback. An edited title renders as a single gradient headline; unedited falls back to
  //    the two-part design headline. (lib/siteCopy degrades to all-null when the backend is absent.)
  //  • article/guide landings, linked from the homepage so they inherit real internal links instead
  //    of being sitemap-only orphans (see fetchArticleLandings). Empty list ⇒ the band renders
  //    nothing. The cap is deliberately above the seeded count: a low cap silently dropped the tail
  //    of the slug ordering (v2rayng-config landed there), leaving exactly the pages this band links.
  //  • /config + /stats for the two hero chips that carry a number (lib/publicData).
  const [copy, articles, config, stats] = await Promise.all([
    fetchSiteCopy(locale),
    fetchFeaturedArticles(4),
    fetchPublicConfig(),
    fetchPublicStats(),
  ]);
  // The translator takes the panel's overrides as its top layer, so every allowlisted design-copy
  // key on this page is editable without a redeploy. With none set it behaves exactly as before.
  const t = translator(locale, copy.overrides);
  // The two number chips state REAL figures or nothing: the renewal window is the operator's
  // setting, and the social proof is the delivered-configs count — the old «۲۴ ساعت» and
  // «+۱۲٬۰۰۰ کاربر» were constants that no setting or count could ever move.
  // (`fill` returns null only when a token it needs is missing, so an override that drops the token
  // still renders with the backend down.)
  const renewChip = fill(t("trust3"), {
    h: config?.trial_hours ? faDigits(config.trial_hours, locale) : null,
  });
  const deliveredChip = fill(t("trust4"), { n: deliveredFigure(stats?.configs_delivered, locale) });

  const steps = [
    { t: "how1_t", d: "how1_d" },
    { t: "how2_t", d: "how2_d" },
    { t: "how3_t", d: "how3_d" },
  ] as const;
  return (
    <>
      {/* HERO — on a phone the claim button has to be on the first screen: a one-to-two-line
          subtitle there (the full one returns from 600px), the trust chips AFTER the widget, and a
          compact widget head. DOM order is copy → widget → chips; the desktop grid puts the chips
          back under the copy. The phone's subtitle is its own key (`hero_sub_short`, in the
          site-copy editor's hero group; the long one is the `site_hero_sub` row): an edited
          `site_hero_sub` is four lines on a phone, which is what pushed the button off the
          screen. */}
      <section className="hero" id="hero">
        <div className="container hero-inner">
          <div className="hero-copy">
            <h1>
              {copy.hero_title ? (
                <span className="grad">{copy.hero_title}</span>
              ) : (
                <>
                  {t("hero_h1_a")} <span className="grad">{t("hero_h1_b")}</span>
                </>
              )}
            </h1>
            <p className="sub sub-long">{copy.hero_sub ?? t("hero_sub")}</p>
            <p className="sub sub-short">{t("hero_sub_short")}</p>
          </div>
          <div id="hero-widget">
            <ClaimWidget locale={locale} copy={copy.overrides} preselect={preselect} />
          </div>
          <div className="trust-row">
            <span className="pill">
              <Icon name="check" sw={2.4} />
              {t("trust1")}
            </span>
            <span className="pill">
              <Icon name="check" sw={2.4} />
              {t("trust2")}
            </span>
            {renewChip && (
              <span className="pill">
                <Icon name="check" sw={2.4} />
                {renewChip}
              </span>
            )}
            {deliveredChip && (
              <span className="pill">
                <Icon name="bolt" sw={2.4} />
                {deliveredChip}
              </span>
            )}
          </div>
        </div>
      </section>
      <StickyCta locale={locale} target="#hero-widget" />

      {/* HOW IT WORKS */}
      <section className="sec" id="how">
        <div className="container">
          <div className="sec-head reveal">
            <span className="eyebrow">{t("how_eyebrow")}</span>
            <h2 className="sec-title">{t("how_title")}</h2>
            <p className="sec-sub">{t("how_sub")}</p>
          </div>
          {/* numbered — it is a sequence — and, on a phone, a compact list rather than three tall
              cards (~800px of screen for three sentences) */}
          <ol className="steps reveal">
            {steps.map((s, i) => (
              <li className="step" key={s.t}>
                <span className="num" aria-hidden>
                  {faDigits(i + 1, locale)}
                </span>
                <h3>{t(s.t)}</h3>
                <p>{t(s.d)}</p>
                <span className="conn" />
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* LOCATIONS (live) */}
      <HomeLocations locale={locale} copy={copy.overrides} />

      {/* MORE VOLUME (live reward amounts) */}
      <HomeMissions locale={locale} copy={copy.overrides} />

      {/* APPS (platform-ordered) */}
      <HomeApps locale={locale} copy={copy.overrides} />

      {/* STATS band — the delivered count and uptime are the server's /stats (already fetched for
          the hero chip), so the band renders real figures in the HTML instead of «—» placeholders */}
      <HomeStats locale={locale} stats={stats} />

      {/* FAQ teaser (live accordion) */}
      <HomeFaq locale={locale} copy={copy.overrides} />

      {/* ARTICLES & GUIDES — a few featured articles as cards, server-rendered so the anchors are in
          the raw HTML a crawler sees, and "all articles" for the rest. Thirteen grey title pills
          read as a link farm (and every one of them was repeated in the footer). */}
      {articles.length > 0 && (
        <section className="sec" id="articles">
          <div className="container">
            <div className="sec-head reveal">
              <span className="eyebrow">{t("art_eyebrow")}</span>
              <h2 className="sec-title">{t("art_title")}</h2>
              <p className="sec-sub">{t("art_sub")}</p>
            </div>
            <div className="art-cards four reveal">
              {articles.map((a) => (
                <Link key={a.slug} className="art-card" href={`/l/${a.slug}`}>
                  {/* bdi: fa titles stay readable inside en (LTR) chrome */}
                  <b>
                    <bdi>{a.label}</bdi>
                  </b>
                  <p>
                    <bdi>{a.desc}</bdi>
                  </p>
                  <span className="more">
                    {t("art_read")}
                    <Icon name="arrow" sw={2.2} cls="ic-dir" />
                  </span>
                </Link>
              ))}
            </div>
            <div className="center-more reveal">
              <Link className="link-more" href="/articles">
                {t("art_all")}
                <Icon name="arrow" sw={2.2} cls="ic-dir" />
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* TRUST band */}
      <section className="sec">
        <div className="container">
          <div className="trust-card reveal">
            <div className="trust-shield">
              <Icon name="shield" sw={2} />
            </div>
            <h2 className="sec-title">{t("trust_title")}</h2>
            <p className="sec-sub" style={{ maxWidth: "40rem", marginInline: "auto" }}>
              {t("trust_sub")}
            </p>
            <div className="trust-badges">
              <span className="tb">
                <Icon name="check" sw={2.6} />
                {t("tb1")}
              </span>
              <span className="tb">
                <Icon name="check" sw={2.6} />
                {t("tb2")}
              </span>
              <span className="tb">
                <Icon name="check" sw={2.6} />
                {t("tb3")}
              </span>
            </div>
            <Link className="link-more" href="/privacy">
              {t("trust_link")}
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}

// The delivered-configs count rounded DOWN to the thousand ("12,000+" is a claim the count backs,
// "12,347" reads as a live meter it is not), in the locale's own digits and grouping. Below a
// thousand there is no round figure worth stating, so the chip is hidden.
function deliveredFigure(count: number | undefined, locale: Locale): string | null {
  if (!count || count < 1000) return null;
  const n = Math.floor(count / 1000) * 1000;
  return n.toLocaleString(locale === "fa" ? "fa-IR" : "en-US");
}
