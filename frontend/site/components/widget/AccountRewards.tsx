"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { subscribeToPush } from "@/lib/push";
import { promptInstall, usePwaState } from "@/lib/pwa";
import { Icon } from "@/components/Icon";

// Account rewards card — the daily-claim streak (day-dots) + the three ways to grow the daily
// allowance (invite / install the web app / enable notifications). Unlike the old decorative strip,
// the actions are REAL: install fires the native prompt (or shows the iOS steps), notifications
// actually subscribe, and each chip shows its live state (installed / enabled / blocked). The
// "+N MB" figures come from the public config — never hardcoded.
export function AccountRewards({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, config, reload } = useSite();
  const pwa = usePwaState();

  const [perm, setPerm] = useState<NotificationPermission>("default");
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [modal, setModal] = useState<null | "ios" | "push" | "blocked">(null);
  const pwaClaimed = useRef(false);

  useEffect(() => {
    if (typeof Notification !== "undefined") setPerm(Notification.permission);
  }, []);

  // Running as an installed PWA is itself proof of install — grant the one-time reward once
  // (the backend dedupes, so a repeat is a clean no-op). Gate on `status` being loaded so this
  // rides the already-minted device cookie and can't race a second cookieless mint.
  useEffect(() => {
    if (pwa === "installed" && status && !pwaClaimed.current) {
      pwaClaimed.current = true;
      api
        .claimReward("pwa")
        .then((r) => {
          if (r.ok) void reload();
        })
        .catch(() => {});
    }
  }, [pwa, status, reload]);

  if (!status) return null;

  const inviteCount = Math.max(0, status.referral_count);
  const inviteCap = Math.max(0, status.referral_cap);
  const invitePct = inviteCap > 0 ? Math.min(100, Math.round((inviteCount / inviteCap) * 100)) : 0;
  const link =
    typeof window !== "undefined" ? `${window.location.origin}/?ref=${status.ref_code}` : "";

  function toast(m: string) {
    setFlash(m);
    setTimeout(() => setFlash(null), 1600);
  }

  async function invite() {
    try {
      if (navigator.share) await navigator.share({ title: "GozarX", url: link });
      else {
        await navigator.clipboard.writeText(link);
        toast(t("copied"));
      }
    } catch {
      /* user cancelled the share sheet */
    }
  }

  async function installPwa() {
    if (pwa === "ios") {
      setModal("ios");
      return;
    }
    if (pwa !== "installable") return;
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

  async function confirmPush() {
    setModal(null);
    setBusy("push");
    try {
      const ok = await subscribeToPush(config?.vapid_public_key ?? "", locale);
      setPerm(typeof Notification !== "undefined" ? Notification.permission : "default");
      if (ok) {
        await api.claimReward("push");
        await reload();
        toast("✓");
      }
    } finally {
      setBusy(null);
    }
  }

  const pushConfigured = !!config?.vapid_public_key;

  return (
    <div className="card rewards-card">
      <div className="block-title" style={{ paddingBlockStart: 14 }}>
        <h2>
          <Icon name="gift" sw={2} /> {t("m_title")}
        </h2>
      </div>

      <StreakCard locale={locale} rewardMb={config?.reward_streak_mb} />

      <div className="ledger">
        {/* Invite — always available; distinguished by its progress bar + bare share button,
            not by a coloured amount (the amount matches every other row). */}
        <div className="lrow lead">
          <span className="lmed">
            <Icon name="users" sw={2} />
          </span>
          <div className="lbd">
            <div className="ltt">{t("m_invite")}</div>
            <div className="lprog">
              <div className="ltrack">
                <i style={{ inlineSize: `${invitePct}%` }} />
              </div>
              <span className="lplbl">
                <b>{faDigits(String(inviteCount), locale)}</b> {t("m_of")}{" "}
                {faDigits(String(inviteCap), locale)} {t("m_invites")}
              </span>
              <button className="lshare" type="button" onClick={invite} aria-label={t("referral.share")}>
                <Icon name="share" sw={2} />
              </button>
            </div>
          </div>
          <LAmt mb={config?.reward_referral_mb} locale={locale} />
        </div>

        {pwa !== "unsupported" &&
          (pwa === "installed" ? (
            <LedgerRow
              icon="download"
              title={t("m_pwa")}
              sub={t("m_pwa_done")}
              state="done"
              amountMb={config?.reward_pwa_mb}
              locale={locale}
            />
          ) : config ? (
            // Only once /config is loaded, so the amount never flashes "+0 MB".
            <LedgerRow
              icon="download"
              title={t("m_pwa")}
              sub={t("m_pwa_d")}
              state="earn"
              amountMb={config.reward_pwa_mb}
              locale={locale}
              onClick={installPwa}
              busy={busy === "pwa"}
            />
          ) : null)}

        {pushConfigured &&
          (perm === "granted" ? (
            <LedgerRow
              icon="bell"
              title={t("m_push")}
              sub={t("m_push_done")}
              state="done"
              amountMb={config?.reward_push_mb}
              locale={locale}
            />
          ) : perm === "denied" ? (
            <LedgerRow
              icon="bell"
              title={t("m_push")}
              sub={t("ps_bl_d")}
              state="blocked"
              amountMb={config?.reward_push_mb}
              locale={locale}
              onClick={() => setModal("blocked")}
            />
          ) : (
            <LedgerRow
              icon="bell"
              title={t("m_push")}
              sub={t("m_push_d")}
              state="earn"
              amountMb={config?.reward_push_mb}
              locale={locale}
              onClick={() => setModal("push")}
              busy={busy === "push"}
            />
          ))}
      </div>

      {flash && (
        <div className="toast-wrap">
          <div className="toast">{flash}</div>
        </div>
      )}

      {modal === "ios" && <IosSteps locale={locale} onClose={() => setModal(null)} />}
      {modal === "push" && (
        <PushPrompt
          locale={locale}
          rewardMb={config?.reward_push_mb}
          onConfirm={confirmPush}
          onClose={() => setModal(null)}
        />
      )}
      {modal === "blocked" && <BlockedHint locale={locale} onClose={() => setModal(null)} />}
    </div>
  );
}

// One "+N MB" amount slot — MB inline beside the figure, one solid treatment for every row.
// `muted` dims it for a blocked reward (still shown, since it's recoverable); `busy` shows a spinner.
function LAmt({
  mb,
  locale,
  muted,
  busy,
}: {
  mb?: number;
  locale: Locale;
  muted?: boolean;
  busy?: boolean;
}) {
  if (busy) return <span className="lamt busy">…</span>;
  return (
    <span className={`lamt${muted ? " muted" : ""}`}>
      <span className="lval">
        <span className="lp">+</span>
        <span className="ln">{faDigits(String(mb ?? 0), locale)}</span>
        <span className="lu">MB</span>
      </span>
    </span>
  );
}

// A ledger row for the install / notifications actions. State is carried by the medallion badge —
// green check = earned (done), red ✕ = blocked, no badge = available — while the amount stays
// consistent. Interactive rows (earn / blocked) render as a full-width button for a big tap target.
function LedgerRow({
  icon,
  title,
  sub,
  state,
  amountMb,
  locale,
  onClick,
  busy,
}: {
  icon: string;
  title: string;
  sub: string;
  state: "earn" | "done" | "blocked";
  amountMb?: number;
  locale: Locale;
  onClick?: () => void;
  busy?: boolean;
}) {
  const inner = (
    <>
      <span className="lmed">
        <Icon name={icon} sw={2} />
        {state === "done" && (
          <span className="ldone">
            <Icon name="check" sw={3} />
          </span>
        )}
        {state === "blocked" && (
          <span className="ldone bad">
            <Icon name="x" sw={2.6} />
          </span>
        )}
      </span>
      <span className="lbd">
        <span className="ltt">{title}</span>
        <span className="lsb">{sub}</span>
      </span>
      <LAmt mb={amountMb} locale={locale} muted={state === "blocked"} busy={busy} />
    </>
  );
  if (onClick) {
    return (
      <button className="lrow" type="button" onClick={onClick} disabled={busy}>
        {inner}
      </button>
    );
  }
  return <div className="lrow">{inner}</div>;
}

// Daily-claim streak: `streak_days` dots, filled up to the current run; the "today" dot is the one
// just earned (if today's config is claimed) or the next one to earn. Read-only — the streak
// advances server-side when a config is claimed.
function StreakCard({ locale, rewardMb }: { locale: Locale; rewardMb?: number }) {
  const t = translator(locale);
  const { status } = useSite();
  if (!status || status.streak_days <= 0) return null;

  const days = status.streak_days;
  const count = Math.min(Math.max(status.streak_count, 0), days);
  const claimedToday = !status.can_claim; // holds today's config / within the cooldown window
  const activeIdx = claimedToday ? count - 1 : count; // the highlighted "today" dot

  const dots = Array.from({ length: days }, (_, i) => {
    const cls = `d${i < count ? " on" : ""}${i === activeIdx && i < days ? " today" : ""}`;
    return (
      <span key={i} className={cls}>
        {faDigits(String(i + 1), locale)}
      </span>
    );
  });

  const progress = `${faDigits(String(count), locale)} / ${faDigits(String(days), locale)}`;
  const cap = status.streak_active
    ? t("streak_active_note")
    : `${progress} — ${t("streak_sub")}`;

  return (
    <div className="streak-block">
      <div className="rw-head">
        <span className="rw-t">
          <Icon name="cal" sw={2} /> {t("streak_title")}
        </span>
        {status.streak_active ? (
          <span className="rw">
            <Icon name="bolt" sw={2.2} /> {`+${faDigits(String(rewardMb ?? 0), locale)} ${t("mb_unit")}`}
          </span>
        ) : null}
      </div>
      <div className="streak">{dots}</div>
      <div className="streak-cap">
        {claimedToday ? (
          <>
            <b style={{ color: "var(--success-ink)" }}>{t("streak_today")} ✓</b> ·{" "}
          </>
        ) : null}
        {cap}
      </div>
    </div>
  );
}

function Overlay({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus(); // move focus into the dialog on open
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay open" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal
        tabIndex={-1}
        ref={ref}
        style={{ maxInlineSize: 420 }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

function IosSteps({ locale, onClose }: { locale: Locale; onClose: () => void }) {
  const t = translator(locale);
  const steps = [
    { n: 1, text: t("ios_1"), icon: "share" },
    { n: 2, text: t("ios_2"), icon: "download" },
    { n: 3, text: t("ios_3"), icon: "check" },
  ] as const;
  return (
    <Overlay onClose={onClose}>
      <h3 style={{ marginBlockEnd: 12 }}>{t("inst_h")}</h3>
      <div className="ios-steps">
        {steps.map((s) => (
          <div className="ios-step" key={s.n}>
            <span className="ios-n">{faDigits(String(s.n), locale)}</span>
            <span className="ios-t">{s.text}</span>
            <span className="ios-badge">
              <Icon name={s.icon} sw={2} />
            </span>
          </div>
        ))}
      </div>
      <button className="btn ghost block" style={{ marginBlockStart: 14 }} onClick={onClose}>
        {t("common.close")}
      </button>
    </Overlay>
  );
}

function PushPrompt({
  locale,
  rewardMb,
  onConfirm,
  onClose,
}: {
  locale: Locale;
  rewardMb?: number;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = translator(locale);
  const reasons = [
    { icon: "download", tt: t("pre_1t"), dd: t("pre_1d") },
    { icon: "gauge", tt: t("pre_2t"), dd: t("pre_2d") },
    { icon: "bell", tt: t("pre_3t"), dd: t("pre_3d") },
  ] as const;
  return (
    <Overlay onClose={onClose}>
      <div className="push-head">
        <span className="push-ic">
          <Icon name="bell" sw={2} />
        </span>
        <div>
          <h3>{t("pre_h")}</h3>
          <p className="msub">{t("pre_d")}</p>
        </div>
      </div>
      <div className="plist">
        {reasons.map((r) => (
          <div className="pitem" key={r.tt}>
            <span className="pio">
              <Icon name={r.icon} sw={2} />
            </span>
            <span>
              <span className="pt">{r.tt}</span>
              <span className="pd">{r.dd}</span>
            </span>
          </div>
        ))}
      </div>
      <span className="rw" style={{ display: "inline-flex", alignItems: "center", gap: 4, marginBlock: 4 }}>
        <Icon name="bolt" sw={2.2} /> {`+${faDigits(String(rewardMb ?? 0), locale)} ${t("mb_unit")}`}
      </span>
      <div style={{ display: "flex", gap: 10, marginBlockStart: 10 }}>
        <button className="btn ghost block" onClick={onClose}>
          {t("pre_no")}
        </button>
        <button className="btn block" onClick={onConfirm}>
          <Icon name="bell" sw={2.2} /> {t("pre_on")}
        </button>
      </div>
    </Overlay>
  );
}

function BlockedHint({ locale, onClose }: { locale: Locale; onClose: () => void }) {
  const t = translator(locale);
  return (
    <Overlay onClose={onClose}>
      <div className="push-head">
        <span className="push-ic" style={{ background: "var(--danger-surface)", color: "var(--danger-ink)" }}>
          <Icon name="bell" sw={2} />
        </span>
        <div>
          <h3>{t("ps_bl_h")}</h3>
          <p className="msub">{t("ps_bl_d")}</p>
        </div>
      </div>
      <p className="hint" dangerouslySetInnerHTML={{ __html: t("ps_bl_hint") }} />
      <button className="btn ghost block" style={{ marginBlockStart: 14 }} onClick={onClose}>
        {t("common.close")}
      </button>
    </Overlay>
  );
}
