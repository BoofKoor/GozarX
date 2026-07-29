"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ClaimResponse } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";
import { Icon } from "@/components/Icon";
import { locName } from "@/components/widget/flags";
import { AppButtons, CopyField, Countdown, Flag, UsageMeter } from "@/components/widget/pieces";
import { Missions } from "@/components/widget/Missions";

type Mode = "idle" | "provisioning";

// ---- courtesy auto-scroll helpers -------------------------------------------------------------
// The widget's height changes a lot across its states (a 22-location picker vs. a compact config
// card), and the browser keeps the old scroll offset across those re-renders — stranding the user
// below the new content. These helpers nudge the viewport the MINIMAL standard way, always
// honouring the user's reduced-motion preference.
const scrollBehavior = (): ScrollBehavior =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

/** Reveal `el` only if needed — `block:"nearest"` is a no-op when it's already fully visible. */
function revealNearest(el: HTMLElement | null) {
  el?.scrollIntoView({ block: "nearest", behavior: scrollBehavior() });
}

// Faithful reproduction of docs/website/design/phase-1-claim-widget.html — the 8-state claim widget.
// State is derived from the live /status; class names match the ported design CSS exactly.
// `preselect` (a location remark NAME, e.g. from an SEO landing's location_remark) pre-picks that
// location once the live list arrives — landing on «کانفیگ آلمان» starts with آلمان selected.
export function ClaimWidget({
  locale,
  compact = false,
  preselect,
}: {
  locale: Locale;
  compact?: boolean;
  preselect?: string;
}) {
  const t = translator(locale);
  const { status, config, locations, loading, offline, reload } = useSite();
  const [picked, setPicked] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<Mode>("idle");
  const [result, setResult] = useState<ClaimResponse | null>(null);
  const [changeLoc, setChangeLoc] = useState(false);
  const [errState, setErrState] = useState(false);
  const [tsError, setTsError] = useState(false); // Turnstile couldn't load / errored — show a retry
  const [tsReset, setTsReset] = useState(0); // bump to reset the widget after a token is consumed

  // Clear the consumed single-use token AND reset the CF widget so the next claim gets a fresh one
  // (clearing the token alone would leave the mounted widget holding the dead token → CTA stuck).
  const clearToken = useCallback(() => {
    setToken("");
    setTsReset((n) => n + 1);
  }, []);

  // Retry a failed Turnstile load: clear the error and remount the widget for a fresh script attempt.
  const retryTurnstile = useCallback(() => {
    setTsError(false);
    setToken("");
    setTsReset((n) => n + 1);
  }, []);

  const needsTurnstile = !!config?.turnstile_enabled && !!config.turnstile_site_key;
  // The admin-starred "popular" location leads the grid (stable sort — the rest keep their panel
  // order) and doubles as the DEFAULT selection, so the CTA is never dead-on-arrival: a visitor
  // can claim with zero taps, and any real pick — or a landing's preselect — overrides it.
  const rawLocs = locations ?? [];
  const popular = config?.popular_location ?? null;
  const popKey = popular ? locName(popular).toLowerCase() : "";
  const isPopular = (l: string) =>
    !!popular && (l === popular || locName(l).toLowerCase() === popKey);
  const locs = popular
    ? [...rawLocs].sort((a, b) => Number(isPopular(b)) - Number(isPopular(a)))
    : rawLocs;
  const defaultPick = locs.find(isPopular) ?? null;

  // Scroll anchors: the outcome card's root (snap-back target after a claim), the claim CTA
  // (revealed after a user pick), and the change-location picker (revealed when it expands).
  const rootRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const changePickRef = useRef<HTMLDivElement>(null);
  // Bumped when a claim attempt RESOLVES (success / cooldown / error) — the snap-back trigger.
  const [outcomeSeq, setOutcomeSeq] = useState(0);

  // USER-initiated pick: reveal the claim button if it sits below the fold (no-op when visible).
  // The landing pages' programmatic preselect calls setPicked directly, so a page load never
  // moves the viewport — only a real tap/click does.
  const pickAndReveal = useCallback((loc: string) => {
    setPicked(loc);
    requestAnimationFrame(() => revealNearest(ctaRef.current));
  }, []);

  // After a claim resolves, the widget re-renders into a (usually shorter) outcome card while the
  // browser keeps the old scroll offset — leaving the user staring below it. Once the new view has
  // PAINTED (double rAF), bring the card's top back under the sticky header — but only when it
  // isn't already in view, so desktop layouts never jump. Focus moves too (without a second
  // scroll) so assistive tech announces the outcome.
  useEffect(() => {
    if (!outcomeSeq) return;
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        const el = rootRef.current;
        if (!el) return;
        const top = el.getBoundingClientRect().top;
        const headerEdge =
          (document.querySelector("header.hd")?.getBoundingClientRect().height ?? 64) + 8;
        if (top < headerEdge - 4 || top > window.innerHeight * 0.6) {
          el.scrollIntoView({ block: "start", behavior: scrollBehavior() });
        }
        el.focus({ preventScroll: true });
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [outcomeSeq]);

  // The server is authoritative once loaded: if it reports no config (e.g. after a device reset),
  // drop any stale optimistic claim result so we don't keep showing a revoked config.
  useEffect(() => {
    if (status && !status.has_config) setResult(null);
  }, [status]);

  // Apply `preselect` once the live location list is in — but only while the user hasn't picked
  // anything themselves (picked===null), so a manual choice always wins. Matches by exact remark
  // or normalized display name (the same tolerance as the "popular" star in the Picker).
  useEffect(() => {
    if (!preselect || picked !== null || !locs.length) return;
    const want = locName(preselect).toLowerCase();
    const hit = locs.find((l) => l === preselect || locName(l).toLowerCase() === want);
    if (hit) setPicked(hit);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locations, preselect]);

  const selected = picked ?? defaultPick ?? (compact && locs.length ? locs[0] : null);

  const doClaim = useCallback(async () => {
    if (!selected || mode === "provisioning") return;
    setMode("provisioning");
    setErrState(false);
    try {
      const res = await api.claim(selected, token || undefined);
      clearToken(); // single-use token: clear it AND reset the widget for the next claim
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
      setOutcomeSeq((s) => s + 1); // every resolution re-renders the widget — snap back to its top
    }
  }, [selected, token, mode, reload, clearToken]);

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
    <div ref={ctaRef} className="cta-anchor">
      <CtaBlock
        locale={locale}
        disabled={!selected}
        busy={mode === "provisioning"}
        onClaim={doClaim}
        needsTurnstile={needsTurnstile}
        token={token}
        siteKey={config?.turnstile_site_key ?? ""}
        onToken={setToken}
        onTsError={() => setTsError(true)}
        onTsRetry={retryTurnstile}
        tsError={tsError}
        tsReset={tsReset}
        trialHours={status?.trial_hours}
      />
    </div>
  );

  // ---------- loading ----------
  if (loading) {
    return (
      // Skeleton mirrors the S1 picker's shape (title · location grid · CTA) so it fills the
      // reserved widget height — the resolve into the real picker doesn't visibly jump.
      <div className="widget wskel" aria-busy>
        <div className="skeleton" style={{ height: 40, width: "55%", marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 18, width: "72%", marginBottom: 18 }} />
        <div className="skeleton wskel-grid" style={{ marginBottom: 16 }} />
        <div className="skeleton" style={{ height: 52 }} />
      </div>
    );
  }

  // ---------- S8 panel error ----------
  if (offline || errState) {
    return (
      <div className="widget" ref={rootRef} tabIndex={-1}>
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
      <div className="widget" ref={rootRef} tabIndex={-1}>
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
            <div ref={changePickRef} className="pick-anchor">
              <Picker
                locale={locale}
                locations={locs}
                selected={selected}
                onPick={pickAndReveal}
                popular={config?.popular_location}
              />
              {cta}
            </div>
          ) : (
            /* change-location as an inviting list row: rotating swap chip, label + the REAL count
               of alternative locations, trailing chevron — not just a flat outline button */
            <button
              className="chg-btn"
              onClick={() => {
                setChangeLoc(true);
                clearToken();
                // reveal the picker that just expanded below the card (no-op if it fits on screen)
                requestAnimationFrame(() => revealNearest(changePickRef.current));
              }}
            >
              <span className="ci" aria-hidden>
                <Icon name="swap" sw={2.2} />
              </span>
              <span className="ct">
                <b>{t("change_loc")}</b>
                {locs.length > 1 && (
                  <small>
                    {faDigits(t("chg_more").replace("{n}", String(locs.length - 1)), locale)}
                  </small>
                )}
              </span>
              <Icon name="chevr" sw={2.4} cls="ic-dir chg-chev" />
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
      <div className="widget" ref={rootRef} tabIndex={-1}>
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
        onPick={pickAndReveal}
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
  onTsError,
  onTsRetry,
  tsError,
  tsReset,
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
  onTsError: () => void;
  onTsRetry: () => void;
  tsError: boolean;
  tsReset: number;
  trialHours?: number;
}) {
  const t = translator(locale);
  return (
    <div className="cta-wrap">
      {needsTurnstile && siteKey && (
        <Turnstile
          siteKey={siteKey}
          locale={locale}
          onToken={onToken}
          onError={onTsError}
          resetSignal={tsReset}
        />
      )}
      {needsTurnstile && tsError && (
        <div className="ts-fail" role="alert">
          <span>
            <Icon name="warn" sw={2} /> {t("ts_fail")}
          </span>
          <button type="button" className="ts-retry" onClick={onTsRetry}>
            {t("ts_retry")}
          </button>
        </div>
      )}
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
      else if (await copyText(link)) {
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
