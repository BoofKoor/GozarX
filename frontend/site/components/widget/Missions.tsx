"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { subscribeToPush } from "@/lib/push";

// "Want more daily volume?" strip — invite (Web Share), install PWA, enable notifications. Reward
// amounts come from the site_* settings (not exposed to the client), so the chips show the action,
// not a hardcoded MB figure. Dismissible.
export function Missions({ locale, refCode }: { locale: Locale; refCode: string }) {
  const t = translator(locale);
  const { config, reload } = useSite();
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  if (hidden) return null;

  const link = typeof window !== "undefined" ? `${window.location.origin}/?ref=${refCode}` : "";

  function toast(m: string) {
    setFlash(m);
    setTimeout(() => setFlash(null), 1800);
  }

  async function invite() {
    try {
      if (navigator.share) await navigator.share({ title: "GozarX", url: link });
      else {
        await navigator.clipboard.writeText(link);
        toast(t("copied"));
      }
    } catch {
      /* cancelled */
    }
  }
  async function claimPwa() {
    setBusy("pwa");
    try {
      await api.claimReward("pwa");
      await reload();
      toast("✓");
    } finally {
      setBusy(null);
    }
  }
  async function enablePush() {
    setBusy("push");
    try {
      const ok = await subscribeToPush(config?.vapid_public_key ?? "", locale);
      if (ok) await api.claimReward("push");
      await reload();
      toast(ok ? "✓" : "—");
    } finally {
      setBusy(null);
    }
  }

  const chips = [
    { key: "invite", icon: <UsersIcon />, title: t("m_invite"), desc: t("m_invite_d"), action: invite, cta: t("share") },
    { key: "pwa", icon: <DownloadIcon />, title: t("m_pwa"), desc: t("m_pwa_d"), action: claimPwa, cta: "＋" },
    { key: "push", icon: <BellIcon />, title: t("m_push"), desc: t("m_push_d"), action: enablePush, cta: "＋" },
  ];

  return (
    <div className="missions">
      <div className="m-head">
        <span className="m-title">
          <GiftIcon /> {t("m_title")}
        </span>
        <button className="m-x" aria-label={t("common.close")} onClick={() => setHidden(true)}>
          ✕
        </button>
      </div>
      <div className="m-chips">
        {chips.map((c) => (
          <div key={c.key} className="m-chip">
            <span className="m-ic" aria-hidden>{c.icon}</span>
            <div className="m-body">
              <strong>{c.title}</strong>
              <span>{c.desc}</span>
            </div>
            <button className="btn secondary m-do" disabled={busy === c.key} onClick={c.action}>
              {busy === c.key ? "…" : c.cta}
            </button>
          </div>
        ))}
      </div>
      {flash && <div className="toast-wrap"><div className="toast">{flash}</div></div>}
    </div>
  );
}

function GiftIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M20 12v9H4v-9M2 7h20v5H2zM12 22V7M12 7S9 2 6.5 3.5 8 7 12 7ZM12 7s3-5 5.5-3.5S16 7 12 7Z" /></svg>; }
function UsersIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" /></svg>; }
function DownloadIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>; }
function BellIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" /></svg>; }
