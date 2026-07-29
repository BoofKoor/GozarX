"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { type Locale, timeAgo, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { api } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { AccountRewards } from "@/components/widget/AccountRewards";
import { TransferCard } from "@/components/TransferCard";
import { Flag } from "@/components/widget/pieces";
import { locName } from "@/components/widget/flags";
import { hasPushSubscription, subscribeToPush } from "@/lib/push";

// My status — faithful reproduction of docs/website/design/phase-6-status.html (dashboard view):
// page head + identity note, live stat row (usage ring / time left / daily volume / invites),
// main grid (config+claim via the shared ClaimWidget • settings), device-transfer card, and a
// destructive "reset this device" row with a confirm dialog. Device-identity based — no login.
export function StatusView({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, config, offline, reload } = useSite();

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
              <h2>
                <Icon name="clock" sw={2} /> {t("hist_title")}
              </h2>
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
    if (await copyText(handle)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
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
  // "On" = permission granted AND a live push subscription — granted alone (e.g. allowed from the
  // browser's own settings) delivers nothing, so the switch must still read as off and stay tappable.
  const [pushSub, setPushSub] = useState(false);
  const [themeState, setThemeState] = useState<string>("");
  useEffect(() => {
    if (typeof Notification !== "undefined") setPerm(Notification.permission);
    void hasPushSubscription().then(setPushSub);
    // Effective theme: an explicit choice sets data-theme; with no cookie the page follows the OS
    // via prefers-color-scheme (data-theme unset), so read the media query in that case.
    const attr = document.getElementById("app")?.getAttribute("data-theme");
    setThemeState(
      attr === "light" || attr === "dark"
        ? attr
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light",
    );
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
      setPushSub(true);
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
        <h2>
          {/* header icon in the rewards gift-tile treatment, so the two side-by-side account
              cards (rewards / settings) share one header rhythm */}
          <span className="htile" aria-hidden>
            <Icon name="sliders" sw={2} />
          </span>
          {t("set_title")}
        </h2>
      </div>
      <div className="srow">
        <span className="si">
          <Icon name="globe" sw={2} />
        </span>
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
        <span className="si">
          <Icon name="contrast" sw={2} />
        </span>
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
        <span className="si">
          <Icon name="bell" sw={2} />
        </span>
        <div className="sk">
          {t("set_notif")} {permTag}
          <div className="skd">{t("set_notif_d")}</div>
        </div>
        <button
          className="switch"
          role="switch"
          aria-checked={perm === "granted" && pushSub}
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
