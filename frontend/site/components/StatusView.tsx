"use client";

import { useEffect, useRef, useState } from "react";
import { type Locale, timeAgo, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { api } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { AccountRewards } from "@/components/widget/AccountRewards";
import { TransferCard } from "@/components/TransferCard";
import { Flag } from "@/components/widget/pieces";
import { locLabel } from "@/components/widget/flags";
import { pushSupported, subscribeToPush, unsubscribeFromPush } from "@/lib/push";
import { usePwaState } from "@/lib/pwa";
import { BlockedHint, IosSteps } from "@/components/widget/Overlay";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { useLocaleSwitch } from "@/lib/prefs";
import { ThemeChoice } from "@/components/ThemeChoice";
import { Announce } from "@/components/Announce";

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
          {/* Reserve the identity bar + caption slot while /status loads so the whole grid doesn't
              drop ~110px when the handle arrives (a status-page CLS). */}
          {status?.handle ? (
            <IdentityBar handle={status.handle} locale={locale} />
          ) : (
            <div className="id-slot" aria-hidden />
          )}
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
        {/* #claim: where the phone menu's "get a config" lands on this page */}
        <div id="claim" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <ClaimWidget locale={locale} />
          <AccountRewards locale={locale} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* null until /config answers: the row keeps its place meanwhile (a disabled switch), so the
              card does not grow under the reader when the answer arrives */}
          <SettingsCard
            locale={locale}
            pushEnabled={config ? !!config.vapid_public_key : null}
            onReload={reload}
          />
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
                      <div className="hn">{locLabel(h.location, locale)}</div>
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
        <Announce text={copied ? t("copied") : ""} />
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
  pushEnabled: boolean | null;
  onReload: () => Promise<void> | void;
}) {
  const t = translator(locale);
  // Push state is SHARED via the provider so this switch and the Rewards card's push mission agree.
  const { config, pushPerm: perm, pushOn, refreshPush } = useSite();
  const [busy, setBusy] = useState(false);
  // language and theme go through lib/prefs, the same code the header and the footer use
  const switchLocale = useLocaleSwitch(locale);
  // Why the switch cannot move, said beside it (C-20) — it used to sit disabled with no word of why,
  // and the fix for "blocked" lived only in the rewards card's modal. Read after mount: the server
  // cannot know what this browser supports.
  const pwa = usePwaState();
  const [supported, setSupported] = useState(true);
  useEffect(() => setSupported(pushSupported()), []);
  const [hint, setHint] = useState<null | "blocked" | "ios">(null);
  async function toggleNotif() {
    if (perm === "denied" || !supported || busy) return; // denied is browser-level; busy: double-tap
    setBusy(true);
    try {
      if (pushOn) {
        // Turn OFF: drop the subscription + stop server sends. The reward already banked stays.
        await unsubscribeFromPush();
      } else {
        // Turn ON: subscribe, then claim the one-time push reward.
        const ok = await subscribeToPush(config?.vapid_public_key ?? "", locale);
        if (ok) {
          await api.claimReward("push");
          await onReload();
        }
      }
      await refreshPush(); // re-sync the shared state so the Rewards card mirrors this switch
    } finally {
      setBusy(false);
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
        <div className="mini-seg" role="group" aria-label={t("set_lang")}>
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
        <ThemeChoice locale={locale} variant="labels" />
      </div>
      {/* No push key on the server means no notification can ever be sent: no row, rather than a
          switch that can only sit there disabled. Unknown yet (null) keeps the row, switch off. */}
      {pushEnabled !== false && (
        <div className="srow">
          <span className="si">
            <Icon name="bell" sw={2} />
          </span>
          <div className="sk">
            {t("set_notif")} {permTag}
            <div className="skd">{t("set_notif_d")}</div>
            {perm === "denied" ? (
              <div className="skd skd-why">
                {t("set_notif_blocked")}{" "}
                <button type="button" className="link-btn" onClick={() => setHint("blocked")}>
                  {t("set_notif_how")}
                </button>
              </div>
            ) : !supported && pwa === "ios" ? (
              <div className="skd skd-why">
                {t("set_notif_ios")}{" "}
                <button type="button" className="link-btn" onClick={() => setHint("ios")}>
                  {t("set_notif_install")}
                </button>
              </div>
            ) : !supported ? (
              <div className="skd skd-why">{t("set_notif_unsupported")}</div>
            ) : null}
          </div>
          <button
            className="switch"
            role="switch"
            aria-checked={pushOn}
            aria-label={t("set_notif")}
            disabled={perm === "denied" || !supported || !pushEnabled || busy}
            onClick={toggleNotif}
          />
        </div>
      )}
      {hint === "blocked" && <BlockedHint locale={locale} onClose={() => setHint(null)} />}
      {hint === "ios" && <IosSteps locale={locale} onClose={() => setHint(null)} />}
    </div>
  );
}

function DangerRow({ locale, onReset }: { locale: Locale; onReset: () => Promise<void> | void }) {
  const t = translator(locale);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // The shared modal contract (Esc, focus in on «انصراف» and back to the button, Tab kept inside,
  // page scroll locked) — except that a reset in flight cannot be dismissed.
  useFocusTrap(dialogRef, () => !busy && setAsking(false), asking, cancelRef);

  async function reset() {
    setBusy(true);
    try {
      await api.resetDevice();
      setAsking(false);
      await onReset();
      // The page re-renders as a new device with nothing to show — which, silently, read as if the
      // tap had done nothing (C-21). A toast says it worked.
      setDone(true);
      window.setTimeout(() => setDone(false), 4000);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {/* mounted for the page's life: a live region inserted together with its text is not read */}
      <div className="toast-wrap" role="status" aria-live="polite">
        {done && (
          <div className="toast">
            <Icon name="check" sw={2.4} />
            {t("reset_done")}
          </div>
        )}
      </div>
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
            ref={dialogRef}
            className="modal"
            role="dialog"
            aria-modal
            aria-labelledby="rm-title"
            aria-describedby="rm-desc"
            tabIndex={-1}
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
              <h2 id="rm-title" className="ov-title" style={{ marginBlockEnd: 8 }}>
                {t("rm_t")}
              </h2>
              <p id="rm-desc" className="msub">
                {t("rm_p")}
              </p>
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
