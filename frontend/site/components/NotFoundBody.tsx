"use client";

import Link from "@/components/Link";
import { faDigits } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { useSite } from "@/lib/useSite";
import { Icon } from "@/components/Icon";

// 404 (C-35): somewhere to go instead of one "back home" button. A search box that lands on the FAQ
// with the words already typed (a plain GET form, so it works before any JS), and the six places
// people actually come for. The number is decoration; the heading says what happened.
// A client component: a not-found boundary gets no params, and reading the request (the old
// getLocale) would make every page that can 404 — every landing — dynamic again. The document
// around it already knows the locale, and hands it down through the site context. Drawn by both
// 404s: app/[lang]/not-found.tsx (a page that called notFound()) and app/global-not-found.tsx (a
// path no route claims).
const LINKS = [
  { href: "/#hero-widget", key: "nav.getConfig", icon: "bolt" },
  { href: "/locations", key: "loc_eyebrow", icon: "pin" },
  { href: "/guides", key: "ft_guides", icon: "book" },
  { href: "/faq", key: "nav_faq", icon: "help" },
  { href: "/status", key: "nav_status", icon: "user" },
  { href: "/contact", key: "contact.title", icon: "mail" },
] as const;

export function NotFoundBody() {
  const { locale } = useSite();
  const t = useT();
  return (
    <section className="sec nf">
      <div className="container nf-inner">
        <p className="nf-code" aria-hidden>
          {faDigits(404, locale)}
        </p>
        <h1>{t("notfound.title")}</h1>
        <p className="nf-sub">{t("notfound.sub")}</p>
        <form className="nf-search" action="/faq" method="get" role="search">
          <div className="idx-search">
            <Icon name="search" sw={2} />
            <input type="search" name="q" placeholder={t("notfound.search")} aria-label={t("notfound.search")} />
          </div>
          <button className="btn" type="submit">
            {t("notfound.go")}
          </button>
        </form>
        <ul className="nf-links">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link href={l.href}>
                <Icon name={l.icon} sw={2} />
                {t(l.key)}
              </Link>
            </li>
          ))}
        </ul>
        <Link href="/" className="link-more">
          {t("notfound.home")}
          <Icon name="arrow" sw={2.2} cls="ic-dir" />
        </Link>
      </div>
    </section>
  );
}
