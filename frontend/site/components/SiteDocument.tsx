import { copyrightYear, dir, type Locale } from "@/lib/i18n";
import { clientCopy, translator } from "@/lib/copy";
import { fetchSiteCopy } from "@/lib/siteCopy";
import { fetchFeaturedArticles } from "@/lib/landing";
import { organizationLd, webSiteLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { PwaRegister } from "@/components/PwaRegister";
import { LogoSymbol } from "@/components/LogoSymbol";
import { RevealObserver } from "@/components/RevealObserver";
import { SiteProvider } from "@/lib/useSite";
import { CopyProvider } from "@/lib/useT";

// The whole document around a page — <html> to the footer — for BOTH ways a page is drawn: the
// root layout of the language trees (app/[lang]/layout.tsx) and the 404 for a path no route claims
// (app/global-not-found.tsx), which Next draws without any layout and so needs the same document
// of its own. One definition, so the 404 cannot drift from the site it belongs to.

// The saved theme cannot be in prerendered HTML, so this puts it on before the first paint — the
// first thing inside #app, ahead of every node it colours. "System" is the absence of the cookie
// (decision D6) and needs nothing: the stylesheet's auto blocks follow the device.
const THEME_SCRIPT =
  '(function(){try{var m=document.cookie.match(/(?:^|; )theme=(light|dark)(?:;|$)/);if(m){document.currentScript.parentNode.setAttribute("data-theme",m[1]);document.documentElement.setAttribute("data-theme",m[1])}}catch(e){}})()';

export async function SiteDocument({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const fontFile = locale === "fa" ? "/fonts/YekanBakh-VF.woff2" : "/fonts/Inter-Variable-latin.woff2";
  // Article landings for the footer's link row — fetched here (server) and passed into the
  // Footer, so every page carries internal links. Degrades to [] with no backend. Five featured,
  // not the whole set: the same thirteen links on every page's footer read as a link farm, and
  // /articles (linked beside them) now gives every article its internal link instead.
  // The site copy with the panel's overrides applied (the same fetch generateMetadata made). The
  // browser gets this ONE locale, resolved, through CopyProvider — not both dictionaries in its
  // JavaScript (C-56).
  const [articles, siteCopy] = await Promise.all([fetchFeaturedArticles(5), fetchSiteCopy(locale)]);
  const t = translator(locale, siteCopy.overrides);
  return (
    <html lang={locale} dir={dir(locale)} suppressHydrationWarning>
      <body suppressHydrationWarning>
        {/* React 19 hoists these into <head>: preload the primary font (faster LCP text paint) and
            emit the sitewide Organization + WebSite JSON-LD. */}
        <link rel="preload" href={fontFile} as="font" type="font/woff2" crossOrigin="anonymous" />
        <JsonLd data={organizationLd()} />
        <JsonLd data={webSiteLd(locale)} />
        <div id="app" data-locale={locale} suppressHydrationWarning>
          <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
          <LogoSymbol />
          {/* the first Tab stop: past the header's links to the page itself (C-41) */}
          <a className="skip-link" href="#main">
            {t("skip_main")}
          </a>
          <CopyProvider copy={clientCopy(locale, siteCopy.overrides)}>
            <SiteProvider locale={locale}>
              <Header locale={locale} />
              <main id="main" tabIndex={-1}>
                {children}
              </main>
              <Footer locale={locale} year={copyrightYear(locale)} articles={articles} copy={siteCopy.overrides} />
              <RevealObserver />
            </SiteProvider>
          </CopyProvider>
        </div>
        <PwaRegister />
      </body>
    </html>
  );
}
