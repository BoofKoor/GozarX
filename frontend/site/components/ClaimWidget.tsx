"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ClaimResponse } from "@/lib/api";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";
import { Icon } from "@/components/Icon";
import { locName } from "@/components/widget/flags";
import { AppButtons, CopyField, Countdown, Flag, UsageMeter } from "@/components/widget/pieces";
import { Missions } from "@/components/widget/Missions";

type Mode = "idle" | "provisioning";

// Faithful reproduction of docs/website/design/phase-1-claim-widget.html — the 8-state claim widget.
// State is derived from the live /status; class names match the ported design CSS exactly.
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

  // The server is authoritative once loaded: if it reports no config (e.g. after a device reset),
  // drop any stale optimistic claim result so we don't keep showing a revoked config.
  useEffect(() => {
    if (status && !status.has_config) setResult(null);
  }, [status]);

  const selected = picked ?? (compact && locs.length ? locs[0] : null);

  const doClaim = useCallback(async () => {
    if (!selected || mode === "provisioning") return;
    setMode("provisioning");
    setErrState(false);
    try {
      const res = await api.claim(selected, token || undefined);
      setToken(""); // Turnstile tokens are single-use — never resubmit a consumed one.
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

  // ---- derive the display state from the live status (status wins; result is the pre-reload view) ----
  const serverHasConfig = !!status?.has_config;
  const link = serverHasConfig ? status?.link ?? null : result?.ok ? result.link ?? null : null;
  const hasConfig = serverHasConfig || (!!result?.ok && !!result.link);
  // Just provisioned this session → celebrate (S3). A change-location claim returns changed=true;
  // that's the calm returning view (S4), not a fresh-claim celebration.
  const fresh = !!result?.ok && !result.changed;
  const exhausted = !!status?.data_exhausted;
  const canClaim = status?.can_claim ?? true;
  const pct =
    status && status.daily_limit_bytes > 0
      ? Math.round((status.usage_bytes / status.daily_limit_bytes) * 100)
      : 0;

  const cta = (
    <CtaBlock
      locale={locale}
      disabled={!selected}
      busy={mode === "provisioning"}
      onClaim={doClaim}
      needsTurnstile={needsTurnstile}
      token={token}
      siteKey={config?.turnstile_site_key ?? ""}
      onToken={setToken}
      trialHours={status?.trial_hours}
    />
  );

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
          <button className="btn" onClick={() => { setErrState(false); void reload(); }}>
            {t("err_retry")}
          </button>
          <a className="btn ghost" href="/faq">{t("err_help")}</a>
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
    const loc = (fresh ? result?.location : status?.location) ?? status?.location ?? "";
    return (
      <div className="widget">
        <div className="cfg">
          <StatusHead
            kind="ok"
            title={fresh ? `${t("succ_title")} 🎉` : t("active_title")}
            sub={fresh ? t("succ_sub") : t("active_sub")}
          />
          {loc && (
            <div className="cfg-loc">
              <Flag name={loc} size={34} />
              <span className="nm">{locName(loc)}</span>
              <span className="ok">
                <Icon name="check" sw={2.6} /> {t("ready")}
              </span>
            </div>
          )}
          <span className="field-label">{t("link_label")}</span>
          <CopyField value={link} locale={locale} />
          <AppButtons link={link} locale={locale} />
          <UsageMeter
            used={status?.usage ?? "0"}
            total={status?.daily_limit ?? "—"}
            pct={pct}
            locale={locale}
            remainingBytes={status ? Math.max(0, status.daily_limit_bytes - status.usage_bytes) : 0}
          />
          {status?.remaining && status.remaining !== "—" ? (
            <>
              <hr className="divider" />
              <Countdown from={status.remaining} label={t("time_left")} locale={locale} onDone={reload} />
            </>
          ) : null}
          {changeLoc ? (
            <>
              <Picker
                locale={locale}
                locations={locs}
                selected={selected}
                onPick={setPicked}
                popular={config?.popular_location}
              />
              {cta}
            </>
          ) : (
            <button
              className="btn secondary block"
              style={{ marginBlockStart: 16 }}
              onClick={() => { setChangeLoc(true); setToken(""); }}
            >
              <Icon name="swap" sw={2} /> {t("change_loc")}
            </button>
          )}
          {fresh && !changeLoc && <Missions locale={locale} refCode={status?.ref_code ?? ""} />}
        </div>
      </div>
    );
  }

  // ---------- S5 cooldown ----------
  if (!canClaim) {
    return (
      <div className="widget">
        <StatusHead kind="wait" title={t("cd_title")} sub={t("cd_sub")} />
        {status?.cooldown ? (
          <div style={{ paddingBlock: 6 }}>
            <Countdown from={status.cooldown} label={t("cd_next")} locale={locale} onDone={reload} />
          </div>
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
        disabled={mode === "provisioning"}
        popular={config?.popular_location}
      />
      {cta}
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
        <Icon name="bolt" sw={2.2} />
      </span>
      <div className="wt">
        <p className="w-title">{t("w_title")}</p>
        {!compact && <p className="w-sub">{t("w_sub")}</p>}
      </div>
      {allowance && (
        <span className="allowance">
          <Icon name="bolt" sw={2} /> {faDigits(t("allowance").replace("{v}", allowance), locale)}
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
  disabled,
  popular,
}: {
  locale: Locale;
  locations: string[];
  selected: string | null;
  onPick: (v: string) => void;
  disabled?: boolean;
  popular?: string | null;
}) {
  const t = translator(locale);
  const popKey = popular ? locName(popular).toLowerCase() : "";
  // The grid is height-capped and scrolls internally (so many locations don't balloon the card). A
  // soft bottom fade hints there's more — shown only while the grid actually overflows AND isn't
  // scrolled to the end, so short lists (no overflow) never get a spurious fade over the last row.
  const gridRef = useRef<HTMLDivElement>(null);
  const [moreBelow, setMoreBelow] = useState(false);
  const updateFade = useCallback(() => {
    const el = gridRef.current;
    if (el) setMoreBelow(el.scrollHeight - el.clientHeight - el.scrollTop > 4);
  }, []);
  useEffect(() => {
    updateFade();
    window.addEventListener("resize", updateFade);
    return () => window.removeEventListener("resize", updateFade);
  }, [updateFade, locations.length]);
  return (
    <>
      <div className="pick-label">
        <span className="l">{t("pick")}</span>
        <span className="c tnum">{faDigits(t("pick_count").replace("{n}", String(locations.length)), locale)}</span>
      </div>
      <div className={`loc-scroll${moreBelow ? " more" : ""}`}>
        <div
          ref={gridRef}
          className="loc-grid"
          role="radiogroup"
          aria-label={t("pick")}
          onScroll={updateFade}
          style={disabled ? { opacity: 0.55, pointerEvents: "none" } : undefined}
        >
          {locations.map((loc) => {
          const on = selected === loc;
          // "Popular" is the admin-flagged location, matched by remark NAME (never index).
          const isPopular = !!popular && (loc === popular || locName(loc).toLowerCase() === popKey);
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
              {isPopular && (
                <span className="loc-rec">
                  <svg className="ic" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M12 2.6l2.7 5.5 6 .9-4.35 4.24 1.03 6L12 16.9l-5.38 2.84 1.03-6L3.3 9l6-.9z" />
                  </svg>
                  {t("rec")}
                </span>
              )}
              <span className="loc-check" aria-hidden>
                <Icon name="check" sw={2.6} />
              </span>
              <span className="flag-wrap">
                <Flag name={loc} size={40} />
                <span className="loc-online" aria-hidden />
              </span>
              <span className="nm">{locName(loc)}</span>
            </button>
          );
          })}
        </div>
      </div>
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
        {busy ? (
          <>
            <span className="spinner" /> {t("cta_prep")}
          </>
        ) : (
          <>
            <Icon name="bolt" sw={2.2} />
            {t("cta_get")}
            <Icon name="arrow" sw={2.4} cls="ic-dir" />
          </>
        )}
      </button>
      <div className="reassure">
        <span className="r"><Icon name="check" sw={2.6} /> {t("reassure1")}</span>
        <span className="r"><Icon name="check" sw={2.6} /> {t("reassure2")}</span>
        <span className="r"><Icon name="check" sw={2.6} /> {faDigits(t("reassure3").replace("{h}", String(trialHours ?? 24)), locale)}</span>
      </div>
      <div className="antibot">
        <Icon name="shield" sw={2} /> {t("antibot")}
      </div>
    </div>
  );
}

function StatusHead({ kind, title, sub }: { kind: "ok" | "wait" | "warn"; title: string; sub: string }) {
  const icon = kind === "ok" ? "check" : kind === "wait" ? "clock" : "warn";
  return (
    <div className="status-head">
      <div className={`status-ic ${kind}`} aria-hidden>
        <Icon name={icon} sw={2.2} />
      </div>
      <div>
        <p className="st-t">{title}</p>
        <p className="st-d">{sub}</p>
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
      <div className={`state-art ${kind}`} aria-hidden>
        <Icon name={kind === "empty" ? "globe" : "plug"} sw={1.9} />
      </div>
      <p className="ct">{title}</p>
      <p className="cd2">{sub}</p>
      <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
        {children}
      </div>
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
      <div className="rt">
        <Icon name="spark" sw={2.2} /> {t("revive_t")}
      </div>
      {/* revive_d is verbatim design copy (a build-time constant in design-copy.ts) with intentional
          <b> emphasis — never user/API data — so rendering it as HTML is safe. */}
      <p className="rd" dangerouslySetInnerHTML={{ __html: t("revive_d") }} />
      <span className="field-label" style={{ marginBlockEnd: 8 }}>
        {t("invite_label")}
      </span>
      <div className="copyfield">
        <code dir="ltr">{link}</code>
        <button className="btn secondary" style={{ flex: "none" }} onClick={share}>
          <Icon name="share" sw={2} /> {copied ? t("copied") : t("share")}
        </button>
      </div>
    </div>
  );
}
