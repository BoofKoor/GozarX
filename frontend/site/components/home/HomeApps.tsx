"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type Locale, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

// APPS section — the design's `.approw` of `.appcard`s, ordered by the detected platform. Real app
// set: v2rayNG · Streisand · Happ (never Hiddify). Platform labels are app facts, not economic
// numbers. Each card links to the connection guides.
const APPS: Record<string, { n: string; icon: string; pf: string }> = {
  v2rayng: { n: "v2rayNG", icon: "/icons/v2rayng.png", pf: "Android" },
  streisand: { n: "Streisand", icon: "/icons/streisand.webp", pf: "iOS · macOS" },
  happ: { n: "Happ", icon: "/icons/happ.webp", pf: "iOS · Android · Desktop" },
};
const ORDER: Record<string, string[]> = {
  ios: ["streisand", "happ", "v2rayng"],
  android: ["v2rayng", "happ", "streisand"],
  desktop: ["happ", "v2rayng", "streisand"],
};
function detectPlatform(): "ios" | "android" | "desktop" {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return "android";
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1))
    return "ios";
  return "desktop";
}

export function HomeApps({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const [platform, setPlatform] = useState<"ios" | "android" | "desktop">("desktop");
  useEffect(() => setPlatform(detectPlatform()), []);
  const order = ORDER[platform] ?? ORDER.desktop;

  return (
    <section className="sec" id="apps-sec" style={{ background: "var(--sunken)" }}>
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("app_eyebrow")}</span>
          <h2 className="sec-title">{t("app_title")}</h2>
          <p className="sec-sub">{t("app_sub")}</p>
        </div>
        <div className="approw reveal">
          {order.map((id) => (
            <Link key={id} className="appcard" href="/guides">
              <span className="big-ico">
                <img src={APPS[id].icon} alt="" width={52} height={52} />
              </span>
              <span className="at">
                <span className="an">{APPS[id].n}</span>
                <span className="ap">{APPS[id].pf}</span>
              </span>
              <span className="ag">
                <Icon name="arrow" sw={2.2} cls="ic-dir" />
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
