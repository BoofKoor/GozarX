"use client";

import { useEffect, useRef, useState } from "react";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { flagCC, locName } from "@/components/widget/flags";
import { Icon } from "@/components/Icon";

// ---- Flag: circular SVG (public/flags/{cc}.svg), fallback = tinted initials tile ----
export function Flag({ name, size = 40 }: { name: string; size?: number }) {
  const cc = flagCC(name);
  const style = { inlineSize: size, blockSize: size } as const;
  if (cc) {
    return <img className="flag" src={`/flags/${cc}.svg`} alt="" style={style} loading="lazy" />;
  }
  return (
    <span className="flag flag-fallback" style={style} aria-hidden>
      {locName(name).slice(0, 2).toUpperCase()}
    </span>
  );
}

// ---- CopyField: LTR monospace island + copy button (design `.copyfield`) ----
export function CopyField({ value, locale }: { value: string; locale: Locale }) {
  const t = translator(locale);
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked */
    }
  }
  return (
    <div className="copyfield">
      <code dir="ltr">{value}</code>
      <button className={`btn${copied ? " copied" : ""}`} onClick={copy} type="button">
        {copied ? t("copied") : t("copy")}
      </button>
    </div>
  );
}

// ---- AppButtons: platform-aware v2rayNG / Streisand / Happ (copy the link for that app) ----
const APPS: Record<string, { n: string; icon: string }> = {
  v2rayng: { n: "v2rayNG", icon: "/icons/v2rayng.png" },
  streisand: { n: "Streisand", icon: "/icons/streisand.webp" },
  happ: { n: "Happ", icon: "/icons/happ.webp" },
};
const PLATFORM_APPS: Record<string, string[]> = {
  ios: ["streisand", "happ"],
  android: ["v2rayng", "happ"],
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

export function AppButtons({ link, locale }: { link: string; locale: Locale }) {
  const t = translator(locale);
  const [platform, setPlatform] = useState<"ios" | "android" | "desktop">("desktop");
  const [flash, setFlash] = useState<string | null>(null);
  useEffect(() => setPlatform(detectPlatform()), []);
  const label = platform === "ios" ? t("open_ios") : platform === "android" ? t("open_android") : t("open_in");
  async function openIn(name: string) {
    try {
      await navigator.clipboard.writeText(link);
      setFlash(name);
      setTimeout(() => setFlash(null), 1400);
    } catch {
      /* ignore */
    }
  }
  return (
    <div className="apps">
      <span className="lbl">{label}</span>
      <div className="apps-row">
        {(PLATFORM_APPS[platform] ?? PLATFORM_APPS.desktop).map((key) => (
          <button key={key} className="app-btn" type="button" onClick={() => openIn(key)}>
            <img className="app-ico" src={APPS[key].icon} alt="" width={26} height={26} />
            {flash === key ? t("copied") : APPS[key].n}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---- UsageMeter (design `.meter` > `.row`/`.k`/`.v` + `.bar`) ----
export function UsageMeter({
  used,
  total,
  pct,
  locale,
}: {
  used: string;
  total: string;
  pct: number;
  locale: Locale;
}) {
  const t = translator(locale);
  const cls = pct >= 100 ? "bar full" : pct >= 80 ? "bar warn" : "bar";
  return (
    <div className="meter">
      <div className="row">
        <span className="k">
          <Icon name="gauge" sw={2} />
          {t("usage")}
        </span>
        <span className="v tnum">
          {faDigits(used, locale)} {t("of")} {faDigits(total, locale)}
        </span>
      </div>
      <div className={cls}>
        <i style={{ inlineSize: `${Math.min(100, Math.max(0, pct))}%` }} />
      </div>
    </div>
  );
}

// ---- Countdown: parse "Xh Ym Zs" (incl. Persian digits) → live segmented HH:MM:SS (design `.cd`) ----
function toSeconds(s: string): number {
  const norm = s.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d).toString());
  const h = /(\d+)\s*(h|ساعت)/.exec(norm);
  const m = /(\d+)\s*(m|دقیقه|min)/.exec(norm);
  const sec = /(\d+)\s*(s|ثانیه|sec)/.exec(norm);
  return (h ? +h[1] * 3600 : 0) + (m ? +m[1] * 60 : 0) + (sec ? +sec[1] : 0);
}
function pad(n: number) {
  return n.toString().padStart(2, "0");
}
export function Countdown({
  from,
  label,
  locale,
  onDone,
}: {
  from: string;
  label: string;
  locale: Locale;
  onDone?: () => void;
}) {
  const t = translator(locale);
  const [left, setLeft] = useState(() => toSeconds(from));
  const doneRef = useRef(false);
  useEffect(() => {
    setLeft(toSeconds(from));
    doneRef.current = false;
  }, [from]);
  useEffect(() => {
    if (left <= 0) {
      if (!doneRef.current) {
        doneRef.current = true;
        onDone?.();
      }
      return;
    }
    const id = setInterval(() => setLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(id);
  }, [left, onDone]);
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const digits = (n: string) =>
    locale === "fa" ? n.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : n;
  return (
    <>
      <div className="cd-label">{label}</div>
      <div className="cd" dir="ltr">
        <span className="seg">
          <b>{digits(pad(h))}</b>
          <span>{t("cd_h")}</span>
        </span>
        <span className="colon">:</span>
        <span className="seg">
          <b>{digits(pad(m))}</b>
          <span>{t("cd_m")}</span>
        </span>
        <span className="colon">:</span>
        <span className="seg">
          <b>{digits(pad(s))}</b>
          <span>{t("cd_s")}</span>
        </span>
      </div>
    </>
  );
}

// ---- InlineCountdown: plain "H:MM:SS" text that ticks (status stat card `.cd-inline`) ----
export function InlineCountdown({ from, locale }: { from: string; locale: Locale }) {
  const [left, setLeft] = useState(() => toSeconds(from));
  useEffect(() => setLeft(toSeconds(from)), [from]);
  useEffect(() => {
    if (left <= 0) return;
    const id = setInterval(() => setLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(id);
  }, [left]);
  if (toSeconds(from) <= 0) return <span dir="ltr">—</span>;
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const txt = `${h}:${pad(m)}:${pad(s)}`;
  const out = locale === "fa" ? txt.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : txt;
  return <span dir="ltr">{out}</span>;
}
