"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
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
  // Push state is SHARED via the provider so this mission and the status page's Settings switch
  // agree — enabling from one flips the other. `pushOn` = permission granted AND a live subscription
  // (granted alone delivers nothing, so the mission must still read as claimable in that case).
  const { status, config, reload, pushPerm: perm, pushOn, refreshPush } = useSite();
  const pwa = usePwaState();

  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [modal, setModal] = useState<null | "ios" | "push" | "blocked">(null);
  const pwaClaimed = useRef(false);

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
      else if (await copyText(link)) toast(t("copied"));
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
      await refreshPush(); // re-sync the shared push state (also updates the Settings switch)
      if (ok) {
        await api.claimReward("push");
        await reload();
        toast("✓");
      } else if (
        typeof Notification !== "undefined" &&
        Notification.permission !== "denied"
      ) {
        // permission wasn't the blocker → the subscribe/store failed; never fail silently
        toast(t("rw_push_err"));
      }
    } finally {
      setBusy(null);
    }
  }

  const pushConfigured = !!config?.vapid_public_key;

  return (
    <div className="card rewards-card rw2">
      <div className="rw2-head">
        <span className="rw2-gift" aria-hidden>
          <Icon name="gift" sw={2} />
        </span>
        <div>
          <h2>{t("m_title")}</h2>
          <p>{t("rw_sub")}</p>
        </div>
      </div>

      <StreakHero locale={locale} rewardMb={config?.reward_streak_mb} />

      <div className="rw2-list">
        {/* Invite — the whole row shares the invite link; live progress toward the cap. */}
        <button className="rw2-row" type="button" onClick={invite}>
          <span className="rw2-tile brand" aria-hidden>
            <Icon name="users" sw={2} />
          </span>
          <span className="rw2-bd">
            <b>{t("m_invite")}</b>
            <span className="rw2-track" aria-hidden>
              <i style={{ inlineSize: `${invitePct}%` }} />
            </span>
            <small className="rw2-cnt">
              <b>{faDigits(String(inviteCount), locale)}</b> {t("m_of")}{" "}
              {faDigits(String(inviteCap), locale)} {t("m_invites")}
            </small>
          </span>
          <span className="rw2-side">
            <span className="rw2-amt brand">
              +{faDigits(String(config?.reward_referral_mb ?? 0), locale)} <u>MB</u>
            </span>
            <Icon name="share" sw={2} cls="rw2-end" />
          </span>
        </button>

        {pwa !== "unsupported" &&
          (pwa === "installed" ? (
            <MissionRow
              tone="success"
              icon="download"
              badge="check"
              title={t("m_pwa")}
              pill={{ text: t("rw_completed"), tone: "success" }}
              amountMb={config?.reward_pwa_mb}
              end="check"
              locale={locale}
            />
          ) : config ? (
            // Only once /config is loaded, so the amount never flashes "+0 MB".
            <MissionRow
              tone="success"
              icon="download"
              title={t("m_pwa")}
              sub={t("rw_pwa_d")}
              amountMb={config.reward_pwa_mb}
              end="chev"
              locale={locale}
              onClick={installPwa}
              busy={busy === "pwa"}
            />
          ) : null)}

        {pushConfigured &&
          (pushOn ? (
            <MissionRow
              tone="violet"
              icon="bell"
              badge="check"
              title={t("m_push")}
              pill={{ text: t("rw_completed"), tone: "success" }}
              amountMb={config?.reward_push_mb}
              end="check"
              locale={locale}
            />
          ) : perm === "denied" ? (
            <MissionRow
              tone="violet"
              icon="bell"
              badge="lock"
              title={t("m_push")}
              pill={{ text: t("rw_blocked"), tone: "danger" }}
              amountMb={config?.reward_push_mb}
              end="chev"
              locale={locale}
              onClick={() => setModal("blocked")}
            />
          ) : (
            <MissionRow
              tone="violet"
              icon="bell"
              title={t("m_push")}
              sub={t("rw_push_d")}
              pill={{ text: t("rw_available"), tone: "violet" }}
              amountMb={config?.reward_push_mb}
              end="chev"
              locale={locale}
              onClick={() => setModal("push")}
              busy={busy === "push"}
            />
          ))}
      </div>

      <div className="rw2-foot">
        <Icon name="info" sw={2} />
        {t("rw_foot")}
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

// One mission row: tinted icon tile (with an optional check/lock mini-badge), title + state pill
// or sub-line, the "+N MB" amount pill in the row's tone, and a trailing chevron (actionable) or
// check (earned). Interactive rows render as a full-width button for a big tap target.
function MissionRow({
  tone,
  icon,
  badge,
  title,
  sub,
  pill,
  amountMb,
  end,
  locale,
  onClick,
  busy,
}: {
  tone: "brand" | "success" | "violet";
  icon: string;
  badge?: "check" | "lock";
  title: string;
  sub?: string;
  pill?: { text: string; tone: "success" | "violet" | "danger" };
  amountMb?: number;
  end: "chev" | "check";
  locale: Locale;
  onClick?: () => void;
  busy?: boolean;
}) {
  const inner = (
    <>
      <span className={`rw2-tile ${tone}`} aria-hidden>
        <Icon name={icon} sw={2} />
        {badge && (
          <span className={`rw2-mini${badge === "lock" ? " bad" : ""}`}>
            <Icon name={badge} sw={3} />
          </span>
        )}
      </span>
      <span className="rw2-bd">
        <b>{title}</b>
        {sub && <small>{sub}</small>}
        {pill && <span className={`rw2-pill ${pill.tone}`}>{pill.text}</span>}
      </span>
      <span className="rw2-side">
        <span className={`rw2-amt ${tone}`}>
          {busy ? "…" : <>+{faDigits(String(amountMb ?? 0), locale)} <u>MB</u></>}
        </span>
        {end === "check" ? (
          <Icon name="check" sw={2.6} cls="rw2-end ok" />
        ) : (
          <Icon name="chevr" sw={2.4} cls="ic-dir rw2-end" />
        )}
      </span>
    </>
  );
  if (onClick) {
    return (
      <button className="rw2-row" type="button" onClick={onClick} disabled={busy}>
        {inner}
      </button>
    );
  }
  return <div className="rw2-row">{inner}</div>;
}

// Streak hero — progress ring around a flame + "Day N of M", a day rail (check = earned, number =
// ahead, star = the final bonus day) and a live status banner. Read-only: the streak advances
// server-side when a config is claimed.
function StreakHero({ locale, rewardMb }: { locale: Locale; rewardMb?: number }) {
  const t = translator(locale);
  const { status } = useSite();
  if (!status || status.streak_days <= 0) return null;

  const days = status.streak_days;
  const count = Math.min(Math.max(status.streak_count, 0), days);
  const claimedToday = !status.can_claim; // holds today's config / within the cooldown window
  const full = status.streak_active;
  const nextDay = Math.min(count + 1, days);

  // ring: r=19 → C≈119.4; progress arc = count/days
  const C = 2 * Math.PI * 19;
  const arc = (count / days) * C;

  const nodes = Array.from({ length: days }, (_, i) => {
    const done = i < count;
    const isLast = i === days - 1;
    const today = !done && i === count; // the next day to earn
    return (
      <span key={i} className={`rw2-node${done ? " on" : ""}${today ? " today" : ""}${isLast ? " last" : ""}`}>
        {done ? (
          <Icon name="check" sw={3} />
        ) : isLast ? (
          <Icon name="star" sw={2} />
        ) : (
          faDigits(String(i + 1), locale)
        )}
      </span>
    );
  });
  // interleave connector lines between nodes (filled while both ends are earned)
  const rail = nodes.flatMap((n, i) =>
    i === 0 ? [n] : [<i key={`l${i}`} className={`rw2-line${i < count ? " on" : ""}`} />, n],
  );

  // one clean caption line under the rail (the old tinted banner box shouted with the rest)
  const cap = full
    ? { cls: "ok", icon: "bolt", text: t("rw_full"), day: null, amt: true }
    : claimedToday
      ? {
          cls: "ok",
          icon: "check",
          text: t("rw_claimed"),
          day: t("rw_day_n").replace("{n}", faDigits(String(nextDay), locale)),
          amt: false,
        }
      : { cls: "", icon: "bolt", text: t("rw_claim_now"), day: null, amt: false };

  return (
    <div className="rw2-streak">
      <div className="rw2-srow">
        <span className="rw2-ring" aria-hidden>
          <svg viewBox="0 0 44 44">
            <circle className="tr" cx="22" cy="22" r="19" />
            {/* CSS already rotates the whole SVG -90° so the arc starts at 12 o'clock; a
                strokeDashoffset here would rotate it a SECOND −90° (arc starting at 9 o'clock).
                Skip the arc entirely at 0 so the round line-cap doesn't leave a stray dot. */}
            {count > 0 && (
              <circle
                className="pr"
                cx="22"
                cy="22"
                r="19"
                strokeDasharray={`${arc} ${C - arc}`}
              />
            )}
          </svg>
          <Icon name="flame" sw={2} />
        </span>
        <div className="rw2-stxt">
          <b>
            {t("rw_day")
              .replace("{a}", faDigits(String(count), locale))
              .replace("{b}", faDigits(String(days), locale))}
          </b>
          <small>{t("rw_keep")}</small>
        </div>
        <div className="rw2-rail" dir="ltr">
          {rail}
        </div>
      </div>
      <div className="rw2-cap">
        <Icon name={cap.icon} sw={2.6} cls={cap.cls} />
        <span>
          {cap.text}
          {cap.day && (
            <>
              {" "}
              <b>{cap.day}</b>
            </>
          )}
        </span>
        {cap.amt && (
          <b className="amt">{`+${faDigits(String(rewardMb ?? 0), locale)} ${t("mb_unit")}`}</b>
        )}
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
