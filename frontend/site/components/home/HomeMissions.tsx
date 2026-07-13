"use client";

import Link from "next/link";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Icon } from "@/components/Icon";

// MORE VOLUME — the ways to grow the daily allowance, as a horizontal list (icon · title/desc ·
// reward amount). The reward is the REAL configured figure (reward_referral/pwa/push/streak_mb),
// shown as a bold "+N MB" tile — never a generic "more volume" label or a hardcoded number.
const MISSIONS = [
  { t: "mv1_t", d: "mv1_d", ic: "users", key: "reward_referral_mb" },
  { t: "mv2_t", d: "mv2_d", ic: "download", key: "reward_pwa_mb" },
  { t: "mv3_t", d: "mv3_d", ic: "bell", key: "reward_push_mb" },
  { t: "mv4_t", d: "mv4_d", ic: "cal", key: "reward_streak_mb" },
] as const;

export function HomeMissions({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { config } = useSite();

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
              <div className="mvrow" key={m.t}>
                <span className="mi">
                  <Icon name={m.ic} sw={2} />
                </span>
                <div className="mvbd">
                  <h3>{t(m.t)}</h3>
                  <p>{t(m.d)}</p>
                </div>
                <span className="mvamt" aria-label={mb != null ? `+${mb} MB` : undefined}>
                  <b>
                    <bdi dir="ltr">{mb != null ? `+${faDigits(String(mb), locale)}` : "—"}</bdi>
                  </b>
                  {mb != null && <i>MB</i>}
                </span>
              </div>
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
