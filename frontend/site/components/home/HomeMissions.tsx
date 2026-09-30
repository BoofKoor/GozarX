import Link from "@/components/Link";
import type { CopyOverrides, Locale } from "@/lib/i18n";
import type { PublicConfig } from "@/lib/api";
import { translator } from "@/lib/copy";
import { Icon } from "@/components/Icon";
import { MB, formatMb, volumeParts } from "@/lib/format";

// MORE VOLUME — the ways to grow the daily allowance, as a horizontal list (icon · title/desc ·
// reward amount). The reward is the REAL configured figure (reward_referral/pwa/push/streak_mb),
// shown as a bold "+N MB" tile — never a generic "more volume" label or a hardcoded number. Each row
// is a link to where the mission is actually DONE — the rewards card on the account page (C-38): the
// rows lifted on hover like links and went nowhere. A figure the backend did not give is left out
// rather than shown as «—». A server component: `config` is the /config the page reads anyway, so the
// amounts are in the HTML and the band costs no JavaScript.
const MISSIONS = [
  { t: "mv1_t", d: "mv1_d", ic: "users", key: "reward_referral_mb" },
  { t: "mv2_t", d: "mv2_d", ic: "download", key: "reward_pwa_mb" },
  { t: "mv3_t", d: "mv3_d", ic: "bell", key: "reward_push_mb" },
  { t: "mv4_t", d: "mv4_d", ic: "cal", key: "reward_streak_mb" },
] as const;

export function HomeMissions({
  locale,
  config,
  copy,
}: {
  locale: Locale;
  config: PublicConfig | null;
  copy?: CopyOverrides;
}) {
  const t = translator(locale, copy);

  return (
    <section className="sec" id="rewards">
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("mv_eyebrow")}</span>
          <h2 className="sec-title">{t("mv_title")}</h2>
          <p className="sec-sub">{t("mv_sub")}</p>
        </div>
        <div className="mvlist reveal">
          {MISSIONS.map((m) => {
            const mb = config?.[m.key];
            return (
              <Link className="mvrow" key={m.t} href="/status#rewards">
                <span className="mi">
                  <Icon name={m.ic} sw={2} />
                </span>
                <div className="mvbd">
                  <h3>{t(m.t)}</h3>
                  <p>{t(m.d)}</p>
                </div>
                {mb != null && <Amount mb={mb} locale={locale} />}
              </Link>
            );
          })}
        </div>
        <div className="center-more reveal">
          <Link className="link-more" href="/status">
            {t("mv_all")}
          </Link>
        </div>
      </div>
    </section>
  );
}

// The reward tile: the figure over its unit, both in the visitor's language («+۵۰۰» over «مگابایت»).
function Amount({ mb, locale }: { mb: number; locale: Locale }) {
  const { num, unit } = volumeParts(mb * MB, locale);
  return (
    <span className="mvamt" aria-label={`+${formatMb(mb, locale)}`}>
      <b aria-hidden>+{num}</b>
      <i aria-hidden>{unit}</i>
    </span>
  );
}
