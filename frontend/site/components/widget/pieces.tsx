"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
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
// Only apps that exist on THIS system: a Windows visitor was offered v2rayNG (Android only) and
// Streisand (Apple only), and a deep link into an app that is not installed does nothing at all.
type Platform = "ios" | "android" | "macos" | "windows" | "linux" | "desktop";
const PLATFORM_APPS: Record<Platform, string[]> = {
  ios: ["streisand", "happ"],
  android: ["v2rayng", "happ"],
  macos: ["happ", "streisand"],
  windows: ["happ"],
  linux: ["happ"],
  desktop: ["happ", "v2rayng", "streisand"], // unrecognised — offer everything
};
function detectPlatform(): Platform {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent;
  if (/android|cros/i.test(ua)) return "android"; // ChromeOS runs the Android apps
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1))
    return "ios"; // iPadOS reports itself as a Mac with touch
  if (/macintosh|mac os x/i.test(ua)) return "macos";
  if (/windows/i.test(ua)) return "windows";
  if (/linux/i.test(ua)) return "linux";
  return "desktop";
}

export function AppButtons({ link, locale }: { link: string; locale: Locale }) {
  const t = translator(locale);
  // Detect synchronously in the initializer — this component only ever mounts CLIENT-side (inside the
  // config state, after the fetch resolves; the SSR pass shows the skeleton), so navigator is already
  // available on first render. Detecting in an effect instead made the row render 3 apps (column) then
  // flip to 2 (row) on mobile, shrinking the card ~100px under the user's finger (a CLS jump).
  const [platform] = useState<Platform>(detectPlatform);
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
      {/* the deep links assume the app is installed — this is the way out when it is not */}
      <Link className="app-get" href={platform === "desktop" ? "/guides" : `/guides/${platform}`}>
        {t("app_get")}
        <Icon name="chevr" sw={2.4} cls="ic-dir" />
      </Link>
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
// `note` replaces the "used of total" figures with a sentence — a fresh config read «۰ B از ۱ GB».
export function UsageMeter({
  used,
  total,
  pct,
  locale,
  remainingBytes,
  note,
}: {
  used: string;
  total: string;
  pct: number;
  locale: Locale;
  remainingBytes?: number;
  note?: string;
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
        {note ? (
          <span className="v">{note}</span>
        ) : (
          <span className="v tnum">
            <bdi dir="ltr">{faDigits(used, locale)}</bdi> {t("of")}{" "}
            <bdi dir="ltr">{faDigits(total, locale)}</bdi>
          </span>
        )}
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

// ---- Countdown: a live segmented HH:MM:SS to an absolute deadline (design `.cd`) ----
// `deadline` is a client-clock millisecond (lib/time turns the server's instant into one). Seconds
// left are recomputed from the wall clock on every tick, never decremented: background tabs are
// throttled to about one tick a minute, and a counter that decremented would fall minutes behind.
// What happens at zero is the caller's business (see lib/usePoll) — this only draws the time.
function useSecondsLeft(deadline: number): number {
  const [left, setLeft] = useState(() => Math.max(0, Math.round((deadline - Date.now()) / 1000)));
  useEffect(() => {
    const tick = () => {
      const next = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setLeft(next);
      if (next <= 0) window.clearInterval(id);
    };
    const id = window.setInterval(tick, 1000);
    tick();
    return () => window.clearInterval(id);
  }, [deadline]);
  return left;
}

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

export function Countdown({
  deadline,
  label,
  locale,
}: {
  deadline: number;
  label: string;
  locale: Locale;
}) {
  const t = translator(locale);
  const left = useSecondsLeft(deadline);
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  // `.cd-seg`, not `.seg` — `.seg` is the header's pill toggle, and its inline-flex put each unit
  // label beside its digits instead of under them.
  return (
    <>
      <div className="cd-label">{label}</div>
      <div className="cd" dir="ltr">
        <span className="cd-seg">
          <b>{faDigits(pad(h), locale)}</b>
          <span>{t("cd_h")}</span>
        </span>
        <span className="colon" aria-hidden>
          :
        </span>
        <span className="cd-seg">
          <b>{faDigits(pad(m), locale)}</b>
          <span>{t("cd_m")}</span>
        </span>
        <span className="colon" aria-hidden>
          :
        </span>
        <span className="cd-seg">
          <b>{faDigits(pad(s), locale)}</b>
          <span>{t("cd_s")}</span>
        </span>
      </div>
    </>
  );
}
