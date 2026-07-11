import Link from "next/link";
import { type Locale, translator } from "@/lib/i18n";

export function Footer({ locale }: { locale: Locale }) {
  const t = translator(locale);
  return (
    <footer className="site-footer">
      <div className="container foot-grid">
        <div className="foot-col">
          <div className="brand" style={{ marginBottom: 10 }}>
            <span>GozarX</span>
          </div>
          <p className="muted" style={{ maxWidth: "40ch" }}>
            {t("footer.trust")}
          </p>
          <div className="trust-band">
            <span>✓ {t("trust.noSignup")}</span>
            <span>✓ {t("trust.noEmail")}</span>
            <span>✓ {t("trust.private")}</span>
          </div>
        </div>
        <div className="foot-col">
          <h4>{t("nav.home")}</h4>
          <Link href="/">{t("nav.home")}</Link>
          <Link href="/status">{t("nav.status")}</Link>
          <Link href="/guides">{t("nav.guides")}</Link>
          <Link href="/faq">{t("nav.faq")}</Link>
          <Link href="/contact">{t("nav.contact")}</Link>
        </div>
        <div className="foot-col">
          <h4>{t("footer.about")}</h4>
          <Link href="/about">{t("footer.about")}</Link>
          <Link href="/privacy">{t("footer.privacy")}</Link>
          <Link href="/terms">{t("footer.terms")}</Link>
        </div>
      </div>
    </footer>
  );
}
