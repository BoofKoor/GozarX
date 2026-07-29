"use client";

import { type ReactNode, useState } from "react";
import { api } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { subscribeToPush } from "@/lib/push";
import { promptInstall, usePwaState } from "@/lib/pwa";
import { Icon } from "@/components/Icon";

// "Want more daily volume?" strip (design `.missions`) — invite (Web Share), install PWA, enable
// notifications. Actions are REAL: install fires the native prompt, notifications actually
// subscribe. The install chip only appears when the browser can actually install (the full iOS
// flow lives on the account page). Reward MB comes from site_* settings. Dismissible.
export function Missions({ locale, refCode }: { locale: Locale; refCode: string }) {
  const t = translator(locale);
  const { config, reload } = useSite();
  const pwa = usePwaState();
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
      else if (await copyText(link)) toast(t("copied"));
    } catch {
      /* cancelled */
    }
  }
  async function installPwa() {
    setBusy("pwa");
    try {
      const ok = await promptInstall();
      if (ok) {
        await api.claimReward("pwa");
        await reload();
        toast("✓");
      }
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

  const chips: {
    key: string;
    ic: string;
    title: string;
    desc: string;
    action: () => void;
    rw: ReactNode;
  }[] = [
    { key: "invite", ic: "users", title: t("m_invite"), desc: t("m_invite_d"), action: invite, rw: <Icon name="share" sw={2} /> },
  ];
  // Only offer the install chip when the browser can actually install (Chromium prompt captured).
  if (pwa === "installable") {
    chips.push({ key: "pwa", ic: "download", title: t("m_pwa"), desc: t("m_pwa_d"), action: installPwa, rw: "＋" });
  }
  if (config?.vapid_public_key) {
    chips.push({ key: "push", ic: "bell", title: t("m_push"), desc: t("m_push_d"), action: enablePush, rw: "＋" });
  }

  return (
    <div className="missions">
      <div className="missions-head">
        <span className="t">
          <Icon name="gift" sw={2} /> {t("m_title")}
        </span>
        <button className="x-btn" aria-label={t("common.close")} onClick={() => setHidden(true)}>
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
      {flash && (
        <div className="toast-wrap">
          <div className="toast">{flash}</div>
        </div>
      )}
    </div>
  );
}
