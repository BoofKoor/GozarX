"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type CopyOverrides, type Locale, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

// APPS section — the design's `.approw` of `.appcard`s, ordered by the detected platform. Real app
// set: v2rayNG · Streisand · Happ (never Hiddify). Platform labels are app facts, not economic
// numbers. Each card opens the page for THAT app (C-37) — all three used to land on the generic
// /guides index: Happ on the connection guide for the visitor's own platform, v2rayNG and Streisand
// on their articles. `pf` lists platforms; "desktop" is a word, so it is translated.
const APPS: Record<string, { n: string; icon: string; pf: string[] }> = {
  v2rayng: { n: "v2rayNG", icon: "/icons/v2rayng.webp", pf: ["Android"] },
  streisand: { n: "Streisand", icon: "/icons/streisand.webp", pf: ["iOS", "macOS"] },
  happ: { n: "Happ", icon: "/icons/happ.webp", pf: ["iOS", "Android", "desktop"] },
};
const HAPP_GUIDE: Record<Platform, string> = {
  ios: "/guides/ios",
  android: "/guides/android",
  desktop: "/guides/windows",
};
const ARTICLE: Record<string, string> = {
  v2rayng: "/l/v2rayng-config",
  streisand: "/l/streisand-config",
};
type Platform = "ios" | "android" | "desktop";
// Happ is the cross-platform pick — always first + flagged recommended. The remaining two follow the
// detected platform's native-first order.
const REST_ORDER: Record<string, string[]> = {
  ios: ["streisand", "v2rayng"],
  android: ["v2rayng", "streisand"],
  desktop: ["v2rayng", "streisand"],
};
function detectPlatform(): Platform {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return "android";
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1))
    return "ios";
  return "desktop";
}

export function HomeApps({ locale, copy }: { locale: Locale; copy?: CopyOverrides }) {
  const t = translator(locale, copy);
  const [platform, setPlatform] = useState<Platform>("desktop");
  useEffect(() => setPlatform(detectPlatform()), []);
  const order = ["happ", ...(REST_ORDER[platform] ?? REST_ORDER.desktop)];

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
            <Link key={id} className="appcard" href={ARTICLE[id] ?? HAPP_GUIDE[platform]}>
              <img className="big-ico" src={APPS[id].icon} alt="" width={52} height={52} />
              <span className="at">
                <span className="an">
                  {APPS[id].n}
                  {id === "happ" && <span className="app-rec">{t("app_rec")}</span>}
                </span>
                {/* each platform its own isolate: «iOS · Android · دسکتاپ» as one run reorders
                    under a Persian base direction */}
                <span className="ap">
                  {APPS[id].pf.map((p, i) => (
                    <span key={p}>
                      {i > 0 && " · "}
                      <bdi>{p === "desktop" ? t("app_desktop") : p}</bdi>
                    </span>
                  ))}
                </span>
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
