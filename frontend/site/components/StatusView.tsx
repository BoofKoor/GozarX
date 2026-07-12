"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { type Locale, timeAgo, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { api } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { AccountRewards } from "@/components/widget/AccountRewards";
import { TransferCard } from "@/components/TransferCard";
import { Flag, InlineCountdown } from "@/components/widget/pieces";
import { locName } from "@/components/widget/flags";
import { subscribeToPush } from "@/lib/push";

// My status — faithful reproduction of docs/website/design/phase-6-status.html (dashboard view):
// page head + identity note, live stat row (usage ring / time left / daily volume / invites),
// main grid (config+claim via the shared ClaimWidget • settings), device-transfer card, and a
// destructive "reset this device" row with a confirm dialog. Device-identity based — no login.
function faDigits(s: string, locale: Locale) {
  return locale === "fa" ? s.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : s;
}

// A stat value like "252.3 MB" — localize its digits, demote the unit to a small muted span, and
// isolate the whole thing as one LTR run so a Latin number+unit never reorders inside the RTL card
// (bidi rule L2 was rendering "252.3 MB" as "MB 252.3") and never wraps mid-token.
function StatNum({ value, locale }: { value: string; locale: Locale }) {
  const m = /^([\d.,٫٬۰-۹]+)\s+(.+)$/.exec(value);
  if (!m) return <bdi dir="ltr">{faDigits(value, locale)}</bdi>;
  return (
    <bdi dir="ltr">
      {faDigits(m[1], locale)}
      <span className="su">{m[2]}</span>
    </bdi>
  );
}

function MiniRing({ pct, locale }: { pct: number; locale: Locale }) {
  // r must leave room for the 5px stroke inside the 44×44 viewBox (center 22): 19 + 2.5 = 21.5 < 22.
  // At r=20 the stroke overflowed to 22.5 and svg overflow:hidden clipped it at the 4 cardinal points.
  const R = 19;
  const C = 2 * Math.PI * R;
  const off = C * (1 - Math.min(100, Math.max(0, pct)) / 100);
  // Only the ARC is toned (warn ≥75, danger ≥90); the centre % keeps its normal colour.
  const tone = pct >= 90 ? " full" : pct >= 75 ? " warn" : "";
  return (
    <div className="ring-mini">
      <svg viewBox="0 0 44 44">
        <circle className="tk" cx="22" cy="22" r={R} />
        <circle
          className={`vl${tone}`}
          cx="22"
          cy="22"
          r={R}
          strokeDasharray={C}
          strokeDashoffset={off}
        />
      </svg>
      <span className="pct">{faDigits(String(pct), locale)}{locale === "fa" ? "٪" : "%"}</span>
    </div>
  );
}

export function StatusView({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, config, loading, offline, reload } = useSite();

  const pct =
    status && status.daily_limit_bytes > 0
      ? Math.min(100, Math.round((status.usage_bytes / status.daily_limit_bytes) * 100))
      : 0;
  const timeLeft = status?.has_config ? status.remaining : (status?.cooldown ?? "");

  return (
    <div className="container status-page">
      <div className="page-head">
        <div>
          <h1>{t("title")}</h1>
          {status?.handle && <IdentityBar handle={status.handle} locale={locale} />}
        </div>
      </div>

      {offline && (
        <div className="danger-row" role="alert" style={{ marginBlockEnd: 16 }}>
          <div className="dt">
            <div className="dn">{t("status.offline")}</div>
          </div>
        </div>
      )}

      {/* STAT ROW (live) */}
      <div className="grid-stats">
        <div className="card stat">
          <MiniRing pct={pct} locale={locale} />
          <div>
            <div className="sv tnum">
              {loading ? "…" : <StatNum value={status?.usage ?? "—"} locale={locale} />}
            </div>
            {/* The ring already encodes the %, and the "daily volume" card states the limit —
                so the label stays a single word, matching its siblings. */}
            <div className="sl">{t("st_usage")}</div>
          </div>
        </div>
        <div className="card stat">
          <div className="sic">
            <Icon name="clock" sw={2} />
          </div>
          <div>
            <div className="sv cd-inline tnum">
              {timeLeft ? <InlineCountdown from={timeLeft} locale={locale} /> : "—"}
            </div>
            <div className="sl">{t("st_left")}</div>
          </div>
        </div>
        <div className="card stat">
          <div className="sic">
            <Icon name="bolt" sw={2} />
          </div>
          <div>
            <div className="sv tnum">
              <StatNum value={status?.daily_limit ?? "—"} locale={locale} />
            </div>
            <div className="sl">{t("st_alw")}</div>
          </div>
        </div>
        <div className="card stat">
          <div className="sic">
            <Icon name="users" sw={2} />
          </div>
          <div>
            <div className="sv tnum">
              {status ? (
                <bdi dir="ltr">
                  {faDigits(String(status.referral_count), locale)} /{" "}
                  {faDigits(String(status.referral_cap), locale)}
                </bdi>
              ) : (
                "—"
              )}
            </div>
            <div className="sl">{t("st_inv")}</div>
          </div>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="grid-main">
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <ClaimWidget locale={locale} />
          <AccountRewards locale={locale} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <SettingsCard locale={locale} pushEnabled={!!config?.vapid_public_key} onReload={reload} />
          <div className="card hist">
            <div className="block-title">
              <h2>{t("hist_title")}</h2>
            </div>
            {status?.history && status.history.length > 0 ? (
              <div className="hist-list">
                {status.history.map((h, i) => (
                  <div className="hrow" key={`${h.at}-${i}`}>
                    <Flag name={h.location} size={30} />
                    <div className="ht">
                      <div className="hn">{locName(h.location)}</div>
                      <div className="hd2">{timeAgo(h.at, locale)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty">
                <div className="ei">
                  <Icon name="clock" sw={1.8} />
                </div>
                <p className="et">{t("status.noHistory")}</p>
                <p className="ed">{t("status.noHistorySub")}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* DEVICE TRANSFER */}
      <div id="transfer" style={{ marginBlockStart: 16 }}>
        <TransferCard locale={locale} />
      </div>

      {/* DANGER ROW */}
      <DangerRow locale={locale} onReset={reload} />
    </div>
  );
}

// Identity bar — the account handle (GZ-…) as one tidy, self-contained component: an id badge, the
// copyable code, an icon copy button, and a device-transfer action, with a single micro-caption.
// The handle is the user's real, stable, shareable identity (also the referral code + transfer
// anchor). LTR (it's an ASCII code).
function IdentityBar({ handle, locale }: { handle: string; locale: Locale }) {
  const t = translator(locale);
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(handle);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked */
    }
  }
  return (
    <>
      <div className="id-bar">
        <span className="id-icb">
          <Icon name="idcard" sw={2} />
        </span>
        <span className="id-code" dir="ltr">
          {handle}
        </span>
        <button
          className={`id-cp${copied ? " done" : ""}`}
          type="button"
          onClick={copy}
          aria-label={t("copy")}
          title={t("copy")}
        >
          <Icon name={copied ? "check" : "copy"} sw={2} />
        </button>
        <span className="id-sep" aria-hidden />
        <a className="id-tr" href="#transfer">
          <Icon name="swap" sw={2} />
          {t("acc_transfer")}
        </a>
      </div>
      <div className="id-cap">{t("acc_cap")}</div>
    </>
  );
}

function SettingsCard({
  locale,
  pushEnabled,
  onReload,
}: {
  locale: Locale;
  pushEnabled: boolean;
  onReload: () => Promise<void> | void;
}) {
  const t = translator(locale);
  const router = useRouter();
  const { config } = useSite();
  // Init to the SSR-safe defaults, then read the real values on mount to avoid hydration mismatch.
  const [perm, setPerm] = useState<NotificationPermission>("default");
  const [themeState, setThemeState] = useState<string>("");
  useEffect(() => {
    if (typeof Notification !== "undefined") setPerm(Notification.permission);
    setThemeState(document.getElementById("app")?.getAttribute("data-theme") ?? "");
  }, []);

  function setCookie(name: string, value: string) {
    document.cookie = `${name}=${value}; path=/; max-age=${400 * 24 * 3600}; samesite=lax`;
  }
  function switchLocale(next: Locale) {
    if (next === locale) return;
    setCookie("locale", next);
    const html = document.documentElement;
    html.setAttribute("lang", next);
    html.setAttribute("dir", next === "fa" ? "rtl" : "ltr");
    document.getElementById("app")?.setAttribute("data-locale", next);
    router.refresh();
  }
  function setTheme(next: "light" | "dark") {
    setCookie("theme", next);
    document.documentElement.setAttribute("data-theme", next);
    document.getElementById("app")?.setAttribute("data-theme", next);
    setThemeState(next);
  }
  async function toggleNotif() {
    if (perm === "denied") return;
    const ok = await subscribeToPush(config?.vapid_public_key ?? "", locale);
    setPerm(typeof Notification !== "undefined" ? Notification.permission : "default");
    if (ok) {
      await api.claimReward("push");
      await onReload();
    }
  }

  const permTag =
    perm === "denied" ? (
      <span className="perm-tag denied">{t("perm_denied")}</span>
    ) : perm === "granted" ? (
      <span className="perm-tag granted">{t("perm_granted")}</span>
    ) : null;

  return (
    <div className="card settings">
      <div className="block-title" style={{ paddingBlockStart: 14 }}>
        <h2>{t("set_title")}</h2>
      </div>
      <div className="srow">
        <div className="sk">{t("set_lang")}</div>
        <div className="mini-seg">
          <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
            فا
          </button>
          <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
            EN
          </button>
        </div>
      </div>
      <div className="srow">
        <div className="sk">{t("set_theme")}</div>
        <div className="mini-seg">
          <button aria-pressed={themeState === "light"} onClick={() => setTheme("light")}>
            {t("set_theme_l")}
          </button>
          <button aria-pressed={themeState === "dark"} onClick={() => setTheme("dark")}>
            {t("set_theme_d")}
          </button>
        </div>
      </div>
      <div className="srow">
        <div className="sk">
          {t("set_notif")} {permTag}
          <div className="skd">{t("set_notif_d")}</div>
        </div>
        <button
          className="switch"
          role="switch"
          aria-checked={perm === "granted"}
          aria-label={t("set_notif")}
          disabled={perm === "denied" || !pushEnabled}
          onClick={toggleNotif}
        />
      </div>
    </div>
  );
}

function DangerRow({ locale, onReset }: { locale: Locale; onReset: () => Promise<void> | void }) {
  const t = translator(locale);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  // While the confirm dialog is open: move focus into it and let Escape dismiss it.
  useEffect(() => {
    if (!asking) return;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) setAsking(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [asking, busy]);

  async function reset() {
    setBusy(true);
    try {
      await api.resetDevice();
      setAsking(false);
      await onReset();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="danger-row">
        <div className="dt">
          <div className="dn">{t("danger_t")}</div>
          <div className="dd">{t("danger_d")}</div>
        </div>
        <button className="btn danger o" onClick={() => setAsking(true)}>
          <Icon name="trash" sw={2} />
          {t("danger_btn")}
        </button>
      </div>

      {asking && (
        <div className="overlay open" onClick={() => !busy && setAsking(false)}>
          <div
            className="modal"
            role="dialog"
            aria-modal
            aria-labelledby="rm-title"
            style={{ maxInlineSize: 400 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="center">
              <div
                className="expired-ic"
                style={{ background: "var(--danger-surface)", color: "var(--danger-ink)" }}
              >
                <Icon name="trash" sw={2.2} />
              </div>
              <h3 id="rm-title" style={{ marginBlockEnd: 8 }}>{t("rm_t")}</h3>
              <p className="msub">{t("rm_p")}</p>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  ref={cancelRef}
                  className="btn ghost block"
                  disabled={busy}
                  onClick={() => setAsking(false)}
                >
                  {t("rm_cancel")}
                </button>
                <button className="btn danger block" disabled={busy} onClick={reset}>
                  {busy ? "…" : t("rm_confirm")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
