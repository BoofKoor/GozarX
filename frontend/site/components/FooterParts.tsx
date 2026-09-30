"use client";

import Link from "@/components/Link";
import { type Locale, fill } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { formatMb } from "@/lib/format";
import { useLocaleSwitch } from "@/lib/prefs";
import { useSite } from "@/lib/useSite";
import { Icon } from "@/components/Icon";

// The footer's two parts that depend on the visitor, as the only client code in it — the rest of
// the footer is server-rendered links (components/Footer.tsx).

// The band follows the visitor's state (V-09): it asked «هنوز کانفیگ امروزت را نگرفته‌ای؟» of
// people who had — on their own account page, under the card saying their config was live. Someone
// who holds a config (or is waiting out the cooldown) is shown the one thing that still grows it,
// inviting, with the configured reward; once the invite cap is reached that stops being true, so
// the band points at their config instead. Unknown (loading, no backend) keeps the claim band. The
// `.ft-cta` element itself stays put across the switch — StickyCta watches it. A device the
// operator blocked can neither claim nor grow anything (its invites are not credited), so it is
// told the one thing left to it.
export function FooterBand({ locale }: { locale: Locale }) {
  const t = useT();
  const { status, config } = useSite();
  const blocked = status?.status === "blocked";
  const holder = !!status && (status.has_config || !status.can_claim);
  const capped = !!status && status.referral_cap > 0 && status.referral_count >= status.referral_cap;
  const reward = config?.reward_referral_mb ?? 0;
  const band = blocked
    ? { h: t("blk_title"), d: t("blk_sub"), btn: t("blk_contact"), href: "/contact" }
    : !holder
      ? { h: t("ft_cta_h"), d: t("ft_cta_d"), btn: t("ft_cta_btn"), href: "/#hero-widget" }
      : capped
        ? { h: t("ft_cta_mine_h"), d: t("ft_cta_mine_d"), btn: t("sticky_mine"), href: "/status" }
        : {
            h: t("ft_cta_inv_h"),
            d:
              (reward > 0 && fill(t("ft_cta_inv_d"), { v: formatMb(reward, locale) })) ||
              t("ft_cta_inv_d_any"),
            btn: t("ft_cta_inv_btn"),
            href: "/status#rewards",
          };
  return (
    <div className="ft-cta">
      <div className="ft-cta-t">
        <h2>{band.h}</h2>
        <p>{band.d}</p>
      </div>
      <Link className="ft-cta-btn" href={band.href}>
        {band.btn}
        <Icon name="arrow" sw={2.2} cls="ic-dir" />
      </Link>
    </div>
  );
}

export function FooterLangs({ locale }: { locale: Locale }) {
  const t = useT();
  const switchLocale = useLocaleSwitch(locale);
  return (
    <div className="ft-langs" role="group" aria-label={t("set_lang")}>
      <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
        فارسی
      </button>
      <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
        English
      </button>
    </div>
  );
}
