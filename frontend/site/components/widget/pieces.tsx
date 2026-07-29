"use client";

import { useEffect, useRef, useState } from "react";
import { copyText } from "@/lib/clipboard";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { flagCC, locName } from "@/components/widget/flags";
import { Icon } from "@/components/Icon";

// ---- Flag: circular SVG (public/flags/{cc}.svg), fallback = tinted initials tile ----
export function Flag({ name, size = 40 }: { name: string; size?: number }) {
  const cc = flagCC(name);
  const [errored, setErrored] = useState(false);
  const style = { inlineSize: size, blockSize: size } as const;
  if (cc && !errored) {
    return (
      <img
        className="flag"
        src={`/flags/${cc}.svg`}
        alt=""
        style={style}
        loading="lazy"
        onError={() => setErrored(true)}
      />
    );
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
  const [failed, setFailed] = useState(false);
  const codeRef = useRef<HTMLElement>(null);
  async function copy() {
    setFailed(false);
    if (await copyText(value)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
      return;
    }
    // Total failure (rare): select the link so the user can copy it by hand + tell them to.
    setFailed(true);
    const node = codeRef.current;
    if (node) {
      const range = document.createRange();
      range.selectNodeContents(node);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
    }
  }
  return (
    <div className="copyfield">
      {/* the shell owns the box (border stays crisp); its ::after fades the CONTENT's end only */}
      <span className="code-shell">
        <code ref={codeRef} dir="ltr">{value}</code>
      </span>
      <button className={`btn${copied ? " copied" : ""}`} onClick={copy} type="button">
        {copied ? t("copied") : t("copy")}
      </button>
      {failed && <span className="copy-manual">{t("copy_manual")}</span>}
    </div>
  );
}

// ---- AppButtons: platform-aware v2rayNG / Streisand / Happ ----
// Each button is a one-tap DEEP LINK that opens the app and imports THIS config. The exact import
// formats were device-tested against each app:
//   • Happ / Streisand — the config link appended RAW after the verb (it already carries the
//     panel's own percent-encoding, incl. the #remark that becomes the config name); re-encoding
//     it breaks the import.
//   • v2rayNG — its UrlSchemeActivity reads the config from ?url= (url-decoded twice, so the
//     panel's own %-escapes are double-encoded) and takes the config NAME from the DEEP LINK's own
//     trailing #fragment (`parseUri(getQueryParameter("url"), uri.fragment)` → appends `#fragment`
//     when the url lacks one). So the remark goes AFTER the whole link as its fragment — not inside
//     ?url= (which install-config rejects) and not as a ?name= param (which v2rayNG never reads).
const dropFragment = (l: string) => l.split("#", 1)[0];
function remark(l: string): string {
  const hash = l.indexOf("#");
  if (hash < 0) return "";
  try {
    return decodeURIComponent(l.slice(hash + 1));
  } catch {
    return l.slice(hash + 1);
  }
}
const APPS: Record<string, { n: string; icon: string; deeplink: (link: string) => string }> = {
  v2rayng: {
    n: "v2rayNG",
    icon: "/icons/v2rayng.webp",
    deeplink: (l) => {
      const base = `v2rayng://install-config?url=${encodeURIComponent(dropFragment(l))}`;
      const name = remark(l);
      return name ? `${base}#${encodeURIComponent(name)}` : base;
    },
  },
  streisand: { n: "Streisand", icon: "/icons/streisand.webp", deeplink: (l) => `streisand://import/${l}` },
  happ: { n: "Happ", icon: "/icons/happ.webp", deeplink: (l) => `happ://add/${l}` },
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
  useEffect(() => setPlatform(detectPlatform()), []);
  // Each button is purely the deep link — tapping opens the app and imports the config. It does NOT
  // copy anything to the clipboard (the separate "copy" field is there for manual paste).
  return (
    <div className="apps">
      <span className="lbl">
        <Icon name="plus" sw={2.4} />
        {t("app_hint")}
      </span>
      <div className="apps-row">
        {(PLATFORM_APPS[platform] ?? PLATFORM_APPS.desktop).map((key) => (
          <a key={key} className="app-btn" href={APPS[key].deeplink(link)}>
            <img className="app-ico" src={APPS[key].icon} alt="" width={26} height={26} />
            {APPS[key].n}
            {/* trailing chevron: the "this opens something" affordance (the row IS the deep link);
                always → because the button content is an LTR island (Latin app names). */}
            <Icon name="chevr" sw={2.4} cls="app-chev" />
          </a>
        ))}
      </div>
    </div>
  );
}

// Mirror the backend's `human_bytes` (1024-based, 1 decimal, round values drop the ".0") so a
// client-derived "remaining volume" formats identically to the server strings ("800 MB", "1.5 GB").
function humanBytes(n: number): string {
  const fmt = (v: number, u: string) =>
    u === "B" ? `${Math.round(v)} ${u}` : `${v.toFixed(1).replace(/\.0$/, "")} ${u}`;
  let v = Math.max(0, n);
  for (const u of ["B", "KB", "MB", "GB"]) {
    if (v < 1024) return fmt(v, u);
    v /= 1024;
  }
  return fmt(v, "TB");
}

// ---- UsageMeter (design `.meter` > `.row`/`.k`/`.v` + `.bar`) ----
// Passing `remainingBytes` switches on the boxed "metric" layout: a % chip beside the label and a
// "remaining volume" footer (the config card). Without it, the plain meter is used (exhausted state).
export function UsageMeter({
  used,
  total,
  pct,
  locale,
  remainingBytes,
}: {
  used: string;
  total: string;
  pct: number;
  locale: Locale;
  remainingBytes?: number;
}) {
  const t = translator(locale);
  const cls = pct >= 90 ? "bar full" : pct >= 75 ? "bar warn" : "bar";
  const metric = remainingBytes != null;
  const pctTxt = `${faDigits(String(pct), locale)}${locale === "fa" ? "٪" : "%"}`;
  return (
    <div className={`meter${metric ? " metric" : ""}`}>
      <div className="row">
        <span className="k">
          <Icon name="gauge" sw={2} />
          {t("usage")}
          {metric && (
            <span className="pct-chip" dir="ltr">
              {pctTxt}
            </span>
          )}
        </span>
        {/* Each "<number> MB" is bidi-isolated so the Latin unit stays glued to its figure under
            RTL (else it renders reversed, e.g. "MB ۷۰۰.۰ از MB ۶۶۶.۵"). */}
        <span className="v tnum">
          <bdi dir="ltr">{faDigits(used, locale)}</bdi> {t("of")}{" "}
          <bdi dir="ltr">{faDigits(total, locale)}</bdi>
        </span>
      </div>
      <div className={cls}>
        <i style={{ inlineSize: `${Math.min(100, Math.max(0, pct))}%` }} />
      </div>
      {metric && (
        <div className="meter-foot">
          {t("remaining_vol")}{" "}
          <b>
            <bdi dir="ltr">{faDigits(humanBytes(remainingBytes), locale)}</bdi>
          </b>
        </div>
      )}
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

// Seconds remaining, derived from an absolute deadline anchored once per `from` — NOT decremented
// per interval fire. Background tabs are throttled to ~1 tick/minute; a per-fire counter would drift
// minutes slow and fire onDone late. Recomputing from wall-clock every tick stays correct across
// throttling/sleep. The deadline is set in an effect (client-only), so there's no SSR/hydration skew.
function useCountdown(from: string, onDone?: () => void): number {
  const [left, setLeft] = useState(() => toSeconds(from));
  const doneRef = useRef(false);
  useEffect(() => {
    const deadline = Date.now() + toSeconds(from) * 1000;
    doneRef.current = false;
    const tick = () => {
      const next = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setLeft(next);
      if (next <= 0 && !doneRef.current) {
        doneRef.current = true;
        onDone?.();
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [from, onDone]);
  return left;
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
  const left = useCountdown(from, onDone);
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
  const left = useCountdown(from);
  if (toSeconds(from) <= 0) return <span dir="ltr">—</span>;
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const txt = `${h}:${pad(m)}:${pad(s)}`;
  const out = locale === "fa" ? txt.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : txt;
  return <span dir="ltr">{out}</span>;
}
