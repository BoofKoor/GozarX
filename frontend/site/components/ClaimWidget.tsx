"use client";

import { useCallback, useMemo, useState } from "react";
import { api, type ClaimResponse } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";
import { locName } from "@/components/widget/flags";
import { AppButtons, CopyField, Countdown, Flag, UsageMeter } from "@/components/widget/pieces";
import { Missions } from "@/components/widget/Missions";

type Mode = "idle" | "provisioning";

export function ClaimWidget({ locale, compact = false }: { locale: Locale; compact?: boolean }) {
  const t = translator(locale);
  const { status, config, locations, loading, offline, reload } = useSite();
  const [picked, setPicked] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<Mode>("idle");
  const [result, setResult] = useState<ClaimResponse | null>(null);
  const [changeLoc, setChangeLoc] = useState(false);
  const [errState, setErrState] = useState(false);

  const needsTurnstile = !!config?.turnstile_enabled && !!config.turnstile_site_key;
  const locs = locations ?? [];

  // Auto-select the first "popular" (or first) location once loaded, matching the design's preset.
  const selected = picked ?? (compact && locs.length ? locs[0] : null);

  const doClaim = useCallback(async () => {
    if (!selected || mode === "provisioning") return;
    setMode("provisioning");
    setErrState(false);
    try {
      const res = await api.claim(selected, token || undefined);
      if (res.ok) {
        setResult(res);
        setChangeLoc(false);
        await reload();
      } else if (res.reason === "cooldown") {
        await reload();
      } else {
        setErrState(true);
      }
    } catch {
      setErrState(true);
    } finally {
      setMode("idle");
    }
  }, [selected, token, mode, reload]);

  // ---- derive the display state from the live status ----
  const link = result?.link ?? status?.link ?? null;
  const hasConfig = !!link && (result?.ok || status?.has_config);
  const exhausted = !!status?.data_exhausted;
  const canClaim = status?.can_claim ?? true;
  const pct = status && status.daily_limit_bytes > 0
    ? Math.round((status.usage_bytes / status.daily_limit_bytes) * 100)
    : 0;

  // ---------- loading ----------
  if (loading) {
    return (
      <div className="widget" aria-busy>
        <div className="skeleton" style={{ height: 40, width: "55%", marginBottom: 16 }} />
        <div className="skeleton" style={{ height: 120, marginBottom: 14 }} />
        <div className="skeleton" style={{ height: 52 }} />
      </div>
    );
  }

  // ---------- S8 panel error ----------
  if (offline || errState) {
    return (
      <div className="widget">
        <CenterState kind="err" title={t("err_title")} sub={t("err_sub")}>
          <button className="btn cta" onClick={() => { setErrState(false); void reload(); }}>
            {t("err_retry")}
          </button>
          <a className="btn secondary" href="/faq">{t("err_help")}</a>
        </CenterState>
      </div>
    );
  }

  // ---------- S6 revive (data exhausted) ----------
  if (hasConfig && exhausted) {
    return (
      <div className="widget">
        <StatusHead kind="warn" title={t("ex_title")} sub={t("ex_sub")} />
        <UsageMeter used={status?.usage ?? "—"} total={status?.daily_limit ?? "—"} pct={100} locale={locale} />
        <ReviveBlock locale={locale} refCode={status?.ref_code ?? ""} />
      </div>
    );
  }

  // ---------- S3/S4 delivered config ----------
  if (hasConfig && link) {
    const loc = result?.location ?? status?.location ?? "";
    return (
      <div className="widget">
        <StatusHead kind="ok" title={t("active_title")} sub={t("active_sub")} />
        {loc && (
          <div className="cfg-loc">
            <Flag name={loc} size={34} />
            <span className="nm">{locName(loc)}</span>
            <span className="pill ready">{t("ready")}</span>
          </div>
        )}
        <div className="link-block">
          <span className="link-label">{t("link_label")}</span>
          <CopyField value={link} locale={locale} />
        </div>
        <AppButtons link={link} locale={locale} />
        <UsageMeter used={status?.usage ?? "0"} total={status?.daily_limit ?? "—"} pct={pct} locale={locale} />
        {status?.cooldown ? (
          <Countdown from={status.cooldown} label={t("time_left")} locale={locale} onDone={reload} />
        ) : null}
        {changeLoc ? (
          <Picker
            locale={locale}
            locations={locs}
            selected={selected}
            onPick={setPicked}
            status={status}
          />
        ) : (
          <button className="btn secondary block" onClick={() => setChangeLoc(true)}>
            <SwapIcon /> {t("change_loc")}
          </button>
        )}
        {changeLoc && (
          <CtaBlock
            locale={locale}
            disabled={!selected}
            busy={mode === "provisioning"}
            onClaim={doClaim}
            needsTurnstile={needsTurnstile}
            token={token}
            siteKey={config?.turnstile_site_key ?? ""}
            onToken={setToken}
            trialHours={status?.streak_days}
          />
        )}
      </div>
    );
  }

  // ---------- S5 cooldown ----------
  if (!canClaim) {
    return (
      <div className="widget">
        <StatusHead kind="wait" title={t("cd_title")} sub={t("cd_sub")} />
        {status?.cooldown ? (
          <Countdown from={status.cooldown} label={t("cd_next")} locale={locale} onDone={reload} />
        ) : null}
        <Missions locale={locale} refCode={status?.ref_code ?? ""} />
      </div>
    );
  }

  // ---------- S7 no locations ----------
  if (locs.length === 0) {
    return (
      <div className="widget">
        <CenterState kind="empty" title={t("empty_title")} sub={t("empty_sub")}>
          <a className="btn secondary" href="/faq">{t("empty_link")}</a>
        </CenterState>
      </div>
    );
  }

  // ---------- S1 idle (+ S2 provisioning overlay) ----------
  return (
    <div className="widget">
      <WidgetHead locale={locale} allowance={status?.daily_limit} compact={compact} />
      <Picker
        locale={locale}
        locations={locs}
        selected={selected}
        onPick={setPicked}
        status={status}
        disabled={mode === "provisioning"}
      />
      <CtaBlock
        locale={locale}
        disabled={!selected}
        busy={mode === "provisioning"}
        onClaim={doClaim}
        needsTurnstile={needsTurnstile}
        token={token}
        siteKey={config?.turnstile_site_key ?? ""}
        onToken={setToken}
        trialHours={status?.streak_days}
      />
    </div>
  );
}

// ================= sub-parts =================

function WidgetHead({
  locale,
  allowance,
  compact,
}: {
  locale: Locale;
  allowance?: string;
  compact: boolean;
}) {
  const t = translator(locale);
  return (
    <div className="w-head">
      <span className="w-badge" aria-hidden>
        <BoltIcon />
      </span>
      <div className="wt">
        <strong>{t("w_title")}</strong>
        {!compact && <span>{t("w_sub")}</span>}
      </div>
      {allowance && (
        <span className="allowance">
          <BoltIcon /> {t("allowance").replace("{v}", allowance)}
        </span>
      )}
    </div>
  );
}

function Picker({
  locale,
  locations,
  selected,
  onPick,
  status,
  disabled,
}: {
  locale: Locale;
  locations: string[];
  selected: string | null;
  onPick: (v: string) => void;
  status: ReturnType<typeof useSite>["status"];
  disabled?: boolean;
}) {
  const t = translator(locale);
  return (
    <>
      <div className="pick-label">
        <span>{t("pick")}</span>
        <span className="pick-count tnum">{t("pick_count").replace("{n}", String(locations.length))}</span>
      </div>
      <div className="loc-grid" role="radiogroup" aria-label={t("pick")} aria-disabled={disabled}>
        {locations.map((loc, i) => {
          const on = selected === loc;
          return (
            <button
              key={loc}
              className="loc-card"
              role="radio"
              aria-checked={on}
              aria-pressed={on}
              disabled={disabled}
              onClick={() => onPick(loc)}
            >
              {i === 0 && !on && <span className="loc-rec">{t("rec")}</span>}
              <span className="loc-flagwrap">
                <Flag name={loc} size={40} />
                <span className="loc-online" aria-hidden />
              </span>
              <span className="nm">{locName(loc)}</span>
              {on && (
                <span className="loc-check" aria-hidden>
                  <CheckIcon />
                </span>
              )}
            </button>
          );
        })}
      </div>
      {void status}
    </>
  );
}

function CtaBlock({
  locale,
  disabled,
  busy,
  onClaim,
  needsTurnstile,
  token,
  siteKey,
  onToken,
  trialHours,
}: {
  locale: Locale;
  disabled: boolean;
  busy: boolean;
  onClaim: () => void;
  needsTurnstile: boolean;
  token: string;
  siteKey: string;
  onToken: (t: string) => void;
  trialHours?: number;
}) {
  const t = translator(locale);
  return (
    <div className="cta-wrap">
      {needsTurnstile && siteKey && <Turnstile siteKey={siteKey} onToken={onToken} />}
      <button
        className="btn cta"
        disabled={disabled || busy || (needsTurnstile && !token)}
        onClick={onClaim}
      >
        <BoltIcon />
        {busy ? t("cta_prep") : t("cta_get")}
        {!busy && <ArrowIcon />}
      </button>
      <div className="reassure">
        <span><CheckIcon /> {t("reassure1")}</span>
        <span><CheckIcon /> {t("reassure2")}</span>
        <span><CheckIcon /> {t("reassure3").replace("{h}", String(trialHours ?? 24))}</span>
      </div>
      <div className="antibot">
        <ShieldIcon /> {t("antibot")}
      </div>
    </div>
  );
}

function StatusHead({ kind, title, sub }: { kind: string; title: string; sub: string }) {
  const icon = kind === "ok" ? <CheckIcon /> : kind === "wait" ? <ClockIcon /> : <WarnIcon />;
  return (
    <div className="status-head">
      <span className={`sic ${kind}`} aria-hidden>{icon}</span>
      <div className="ti">
        <strong>{title}</strong>
        <span>{sub}</span>
      </div>
    </div>
  );
}

function CenterState({
  kind,
  title,
  sub,
  children,
}: {
  kind: "empty" | "err";
  title: string;
  sub: string;
  children: React.ReactNode;
}) {
  return (
    <div className="center-state">
      <span className={`cs-art ${kind}`} aria-hidden>
        {kind === "empty" ? <GlobeIcon /> : <PlugIcon />}
      </span>
      <strong>{title}</strong>
      <p>{sub}</p>
      <div className="cs-actions">{children}</div>
    </div>
  );
}

function ReviveBlock({ locale, refCode }: { locale: Locale; refCode: string }) {
  const t = translator(locale);
  const [copied, setCopied] = useState(false);
  const link = typeof window !== "undefined" ? `${window.location.origin}/?ref=${refCode}` : "";
  async function share() {
    try {
      if (navigator.share) await navigator.share({ title: "GozarX", url: link });
      else {
        await navigator.clipboard.writeText(link);
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      }
    } catch {
      /* cancelled */
    }
  }
  return (
    <div className="revive">
      <div className="revive-head">
        <SparkIcon />
        <strong>{t("revive_t")}</strong>
      </div>
      <p dangerouslySetInnerHTML={{ __html: t("revive_d").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>") }} />
      <span className="invite-label">{t("invite_label")}</span>
      <div className="copyfield">
        <code>{link}</code>
        <button className="btn secondary" onClick={share}>
          {copied ? t("copied") : t("share")}
        </button>
      </div>
    </div>
  );
}

// icons
function BoltIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M13 2 4.5 13.5H11l-1 8.5 8.5-11.5H12l1-8.5Z" /></svg>; }
function ArrowIcon() { return <svg className="ic ic-dir" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12h14M13 6l6 6-6 6" /></svg>; }
function CheckIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M20 6 9 17l-5-5" /></svg>; }
function SwapIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7" /></svg>; }
function ShieldIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z" /></svg>; }
function ClockIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>; }
function WarnIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 9v4M12 17h.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg>; }
function GlobeIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3.5 3 14 0 18M12 3c-3 3.5-3 14 0 18" /></svg>; }
function PlugIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M9 2v6M15 2v6M7 8h10v3a5 5 0 0 1-10 0V8ZM12 16v6" /></svg>; }
function SparkIcon() { return <svg className="ic" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2Z" /></svg>; }
