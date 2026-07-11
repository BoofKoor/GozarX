"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const arr = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

export function RewardsTeaser({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, config, reload } = useSite();
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  }

  const inviteLink =
    status && typeof window !== "undefined" ? `${window.location.origin}/?ref=${status.ref_code}` : "";

  async function shareInvite() {
    if (!inviteLink) return;
    const data = { title: "GozarX", text: t("referral.sub"), url: inviteLink };
    try {
      if (navigator.share) await navigator.share(data);
      else {
        await navigator.clipboard.writeText(inviteLink);
        flash(t("claim.copied"));
      }
    } catch {
      /* user cancelled — ignore */
    }
  }

  async function claimReward(kind: "pwa" | "push" | "streak") {
    setBusy(kind);
    try {
      const res = await api.claimReward(kind);
      if (res.ok) flash(`+${res.amount_mb ?? ""}${res.amount_mb ? " MB" : "✓"}`.trim());
      else if (res.reason === "already_claimed") flash("✓");
      await reload();
    } catch {
      /* ignore */
    } finally {
      setBusy(null);
    }
  }

  async function enablePush() {
    setBusy("push");
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !config?.vapid_public_key) {
        flash("—");
        return;
      }
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return;
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(config.vapid_public_key),
      });
      const json = sub.toJSON();
      await api.subscribePush({
        endpoint: sub.endpoint,
        p256dh: json.keys?.p256dh ?? "",
        auth: json.keys?.auth ?? "",
        locale,
      });
      await claimReward("push");
    } catch {
      /* ignore */
    } finally {
      setBusy(null);
    }
  }

  const cards = [
    { key: "invite", title: t("rewards.invite"), desc: t("rewards.inviteDesc"), action: shareInvite, label: t("referral.share") },
    { key: "pwa", title: t("rewards.pwa"), desc: t("rewards.pwaDesc"), action: () => claimReward("pwa"), label: "＋" },
    { key: "push", title: t("rewards.push"), desc: t("rewards.pushDesc"), action: enablePush, label: "＋" },
    { key: "streak", title: t("rewards.streak"), desc: t("rewards.streakDesc"), action: () => claimReward("streak"), label: "＋" },
  ] as const;

  return (
    <section>
      <div className="container">
        <span className="eyebrow">{t("rewards.title")}</span>
        <h2 className="mt-2">{t("referral.title")}</h2>
        <p className="lead mt-2">{t("referral.sub")}</p>

        {status && (
          <div className="card card-pad mt-6 stack">
            <div className="between">
              <strong>{t("referral.your")}</strong>
              <span className="chip chip-muted">
                {t("referral.count")}: <span className="tnum">{status.referral_count}/{status.referral_cap}</span>
              </span>
            </div>
            <div className="codebox">{inviteLink}</div>
            <button className="btn btn-primary" onClick={shareInvite}>
              {t("referral.share")}
            </button>
          </div>
        )}

        <div className="missions mt-6">
          {cards.map((c) => (
            <div key={c.key} className="mission" style={{ flex: "1 1 240px" }}>
              <div style={{ flex: 1 }}>
                <strong>{c.title}</strong>
                <div className="hint">{c.desc}</div>
              </div>
              <button className="btn btn-ghost" disabled={busy === c.key} onClick={c.action}>
                {busy === c.key ? "…" : c.label}
              </button>
            </div>
          ))}
        </div>
      </div>
      {toast && (
        <div className="toast-wrap">
          <div className="toast">{toast}</div>
        </div>
      )}
    </section>
  );
}
