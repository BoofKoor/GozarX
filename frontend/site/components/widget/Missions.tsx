"use client";

import { type ReactNode, useState } from "react";
import { api } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { type Locale } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { rewardMessage, shareInvite } from "@/lib/rewards";
import { useSite } from "@/lib/useSite";
import { pushSupported, subscribeToPush } from "@/lib/push";
import { promptInstall, usePwaState } from "@/lib/pwa";
import { Icon } from "@/components/Icon";
import { formatMb } from "@/lib/format";
import { IosSteps } from "@/components/widget/Overlay";

// Closing the strip holds until tomorrow (local midnight) rather than until the next render — it
// used to reappear on every visit, which made the ✕ look broken.
const DISMISS_KEY = "gz_missions_hidden_until";
function dismissedNow(): boolean {
  try {
    return Number(window.localStorage.getItem(DISMISS_KEY) ?? 0) > Date.now();
  } catch {
    return false; // storage blocked (private mode, a strict browser): the strip just shows
  }
}
function dismissUntilTomorrow(): void {
  try {
    const midnight = new Date();
    midnight.setHours(24, 0, 0, 0);
    window.localStorage.setItem(DISMISS_KEY, String(midnight.getTime()));
  } catch {
    /* not persisted — it still hides for this view */
  }
}

// "Want more daily volume?" strip (design `.missions`) — invite (Web Share), install PWA, enable
// notifications. Actions are REAL: install fires the native prompt, notifications actually
// subscribe. The install chip appears where the browser can install — and on iOS as the "Add to
// Home Screen" steps, since web push only exists there for an installed web app. Reward MB comes
// from site_* settings. Dismissible until tomorrow.
export function Missions({ locale, refCode }: { locale: Locale; refCode: string }) {
  const t = useT();
  const { config, reload, pushPerm, pushOn, refreshPush } = useSite();
  const pwa = usePwaState();
  const [hidden, setHidden] = useState(dismissedNow);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [iosSteps, setIosSteps] = useState(false);
  if (hidden) return null;

  const link = typeof window !== "undefined" ? `${window.location.origin}/?ref=${refCode}` : "";

  function toast(m: string) {
    setFlash(m);
    setTimeout(() => setFlash(null), 1800);
  }

  async function invite() {
    if (await shareInvite(link, t)) return;
    if (typeof navigator !== "undefined" && "share" in navigator) return; // a sheet exists; dismissed
    if (await copyText(link)) toast(t("invite_copied"));
  }
  async function installPwa() {
    setBusy("pwa");
    try {
      if (await promptInstall()) {
        const r = await api.claimReward("pwa").catch(() => null);
        await reload();
        toast(rewardMessage(t, locale, r, config?.reward_pwa_mb, "m_pwa_done"));
      }
    } finally {
      setBusy(null);
    }
  }
  async function enablePush() {
    setBusy("push");
    try {
      const ok = await subscribeToPush(config?.vapid_public_key ?? "", locale);
      const r = ok ? await api.claimReward("push").catch(() => null) : null;
      await refreshPush(); // keep the shared push state (status-page switch/mission) in sync
      await reload();
      if (ok) toast(rewardMessage(t, locale, r, config?.reward_push_mb, "m_push_done"));
      else if (Notification.permission === "denied") toast(t("ps_bl_d"));
      else toast(t("rw_push_err"));
    } finally {
      setBusy(null);
    }
  }

  // The amount a chip earns, as a pill — the reason to tap it. `fallback` covers an unset (0) reward.
  const amount = (mb: number | undefined, fallback: ReactNode) =>
    mb && mb > 0 ? <bdi>+{formatMb(mb, locale)}</bdi> : fallback;

  const chips: {
    key: string;
    ic: string;
    title: string;
    desc: string;
    action: () => void;
    rw: ReactNode;
  }[] = [
    {
      key: "invite",
      ic: "users",
      title: t("m_invite"),
      desc: t("m_invite_d"),
      action: invite,
      rw: amount(config?.reward_referral_mb, <Icon name="share" sw={2} />),
    },
  ];
  // Only offer the install chip when the browser can actually install (Chromium prompt captured) —
  // or on iOS, where "install" is three manual steps, and the one way to notifications there too.
  if (pwa === "installable" || pwa === "ios") {
    chips.push({
      key: "pwa",
      ic: "download",
      title: t("m_pwa"),
      desc: pwa === "ios" ? t("m_pwa_ios") : t("m_pwa_d"),
      action: pwa === "ios" ? () => setIosSteps(true) : installPwa,
      rw: amount(config?.reward_pwa_mb, "＋"),
    });
  }
  // Only while it can still be earned HERE: not once notifications are on, not once the visitor has
  // blocked them (the browser would refuse without asking), and not where push does not exist. On
  // an iPhone that has not installed the web app, the install chip above is the way to push.
  if (
    config?.vapid_public_key &&
    !pushOn &&
    pushPerm !== "denied" &&
    pwa !== "ios" &&
    pushSupported()
  ) {
    chips.push({
      key: "push",
      ic: "bell",
      title: t("m_push"),
      desc: t("m_push_d"),
      action: enablePush,
      rw: amount(config?.reward_push_mb, "＋"),
    });
  }

  return (
    <div className="missions">
      <div className="missions-head">
        <span className="t">
          <Icon name="gift" sw={2} /> {t("m_title")}
        </span>
        <button
          className="x-btn"
          aria-label={t("common.close")}
          onClick={() => {
            dismissUntilTomorrow();
            setHidden(true);
          }}
        >
          <Icon name="x" sw={2} />
        </button>
      </div>
      <div className="m-chips">
        {chips.map((c) => (
          <button
            key={c.key}
            className="m-chip"
            type="button"
            disabled={busy === c.key}
            onClick={c.action}
          >
            <span className="mi">
              <Icon name={c.ic} sw={2} />
            </span>
            <span className="mt">
              <span className="mn">{c.title}</span>
              <span className="md">{c.desc}</span>
            </span>
            <span className="rw">{busy === c.key ? "…" : c.rw}</span>
          </button>
        ))}
      </div>
      {/* The live region stays mounted: one inserted together with its text is not announced. */}
      <div className="toast-wrap" role="status">
        {flash && <div className="toast">{flash}</div>}
      </div>
      {iosSteps && <IosSteps locale={locale} onClose={() => setIosSteps(false)} />}
    </div>
  );
}
