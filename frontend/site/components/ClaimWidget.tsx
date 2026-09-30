"use client";

import { type ReactNode, useCallback, useEffect, useId, useRef, useState } from "react";
import Link from "@/components/Link";
import { api, type ClaimResponse, type StatusResponse } from "@/lib/api";
import { type Locale, faDigits, fill } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { clientDeadline } from "@/lib/time";
import { useBackoffPoll, useExpired, useVisiblePoll } from "@/lib/usePoll";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";
import { Icon } from "@/components/Icon";
import { locLabel, locName } from "@/components/widget/flags";
import { formatVolume } from "@/lib/format";
import { type LastConfig, readLastConfig, saveLastConfig } from "@/lib/lastConfig";
import { Flag } from "@/components/widget/Flag";

type Mode = "idle" | "provisioning";
// A claim that did not go through but leaves S1 the right screen: said in place, under the picker,
// instead of the generic error page every failure used to land on.
type Notice = "loc_gone" | "busy" | "ts" | null;
// How the config came back to life, captured at the moment the widget SAW it happen (S6 → live).
interface Revived {
  friend: boolean; // the referral count moved — a friend's first claim did it
  addedBytes: number; // how much the daily allowance grew
}

// ---- the post-claim views, loaded on demand ---------------------------------------------------
// The picker is all a first visit sees, so everything shown only after a claim — the delivered
// config, the countdown, the missions, the revive — lives in `widget/after` and is fetched when it
// is about to be needed: with the claim request itself, or at once in a browser that has held a
// config (`lib/lastConfig`), whose next view is most likely one of them. Until it arrives such a
// view draws the loading skeleton it would have drawn while /status was on its way.
type After = typeof import("@/components/widget/after");
let afterModule: After | null = null;
let afterLoad: Promise<After> | null = null;
function loadAfter(): Promise<After> {
  afterLoad ??= import("@/components/widget/after").then(
    (m) => (afterModule = m),
    (err: unknown) => {
      afterLoad = null; // a failed fetch is tried again the next time it is needed
      throw err;
    },
  );
  return afterLoad;
}
function useAfter(need: boolean): After | null {
  const [, loaded] = useState(0);
  useEffect(() => {
    if (!need || afterModule) return;
    let live = true;
    loadAfter().then(
      () => live && loaded((n) => n + 1),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [need]);
  return afterModule;
}

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

/** Same location: the exact remark, or the same display name (the "popular" star's tolerance). */
function sameLoc(a: string, b: string | null | undefined): boolean {
  return !!b && (a === b || locName(a).toLowerCase() === locName(b).toLowerCase());
}

// Faithful reproduction of docs/website/design/phase-1-claim-widget.html — the 8-state claim widget.
// State is derived from the live /status; class names match the ported design CSS exactly.
// `preselect` (a location remark NAME, e.g. from an SEO landing's location_remark) pre-picks that
// location once the live list arrives — landing on «کانفیگ آلمان» starts with آلمان selected.
export function ClaimWidget({
  locale,
  compact = false,
  preselect,
  title,
}: {
  locale: Locale;
  compact?: boolean;
  preselect?: string;
  /** The picker's heading in place of «کانفیگ رایگان امروز» — a landing names its location. */
  title?: string;
}) {
  const t = useT();
  const { status, statusAt, config, locations, loading, offline, reload, refreshLocations } =
    useSite();
  const [picked, setPicked] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<Mode>("idle");
  const [result, setResult] = useState<ClaimResponse | null>(null);
  const [changeLoc, setChangeLoc] = useState(false);
  const [errState, setErrState] = useState(false);
  const [unavailable, setUnavailable] = useState(false); // the claim said not_ready / no_locations
  const [notice, setNotice] = useState<Notice>(null);
  const [retryPending, setRetryPending] = useState(false); // the one automatic retry after a 429
  const retried = useRef(false);
  const [revived, setRevived] = useState<Revived | null>(null);
  const [tsError, setTsError] = useState(false); // Turnstile couldn't load / errored — show a retry
  const [tsReset, setTsReset] = useState(0); // bump to reset the widget after a token is consumed

  // Background checks go through a QUIET reload: one failed poll must not throw the widget onto its
  // error screen in the middle of a countdown — the next poll simply tries again.
  const poll = useCallback(() => reload({ quiet: true }), [reload]);

  // Clear the consumed single-use token AND reset the CF widget so the next claim gets a fresh one
  // (clearing the token alone would leave the mounted widget holding the dead token → CTA stuck).
  const clearToken = useCallback(() => {
    setToken("");
    setTsReset((n) => n + 1);
  }, []);

  // Stable, because <Turnstile> re-renders the Cloudflare widget whenever its callbacks change: an
  // inline arrow here rebuilt the challenge on every render of the claim widget.
  const onTsError = useCallback(() => setTsError(true), []);

  // Retry a failed Turnstile load: clear the error and remount the widget for a fresh script attempt.
  const retryTurnstile = useCallback(() => {
    setTsError(false);
    setToken("");
    setTsReset((n) => n + 1);
  }, []);

  const needsTurnstile = !!config?.turnstile_enabled && !!config.turnstile_site_key;
  const popular = config?.popular_location ?? null;
  const current = status?.location ?? null;
  // Lead the grid with what the visitor most likely wants, so the collapsed two rows always hold it:
  // when switching, the location in use (marked «فعلی»); otherwise a landing page's promised
  // location, then the admin's "popular" pick. A stable sort — everything else keeps panel order.
  const lead = changeLoc ? current : (preselect ?? null);
  const rank = (l: string) => (sameLoc(l, lead) ? 0 : sameLoc(l, popular) ? 1 : 2);
  const rawLocs = locations ?? [];
  const locs = [...rawLocs].sort((a, b) => rank(a) - rank(b));
  // The popular location doubles as the DEFAULT selection, so the CTA is never dead-on-arrival: a
  // visitor can claim with zero taps, and any real pick — or a landing's preselect — overrides it.
  const defaultPick = rawLocs.find((l) => sameLoc(l, popular)) ?? null;

  // Scroll anchors: the outcome card's root (snap-back target after a claim), the claim CTA
  // (revealed after a user pick), and the change-location picker (revealed when it expands).
  const rootRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const changePickRef = useRef<HTMLDivElement>(null);
  // Bumped when a claim attempt RESOLVES (success / cooldown / error) — the snap-back trigger.
  const [outcomeSeq, setOutcomeSeq] = useState(0);
  // True from the tap until the outcome has been focused: that outcome announces itself through
  // focus, so the live region stays quiet for it (see `announce` below).
  const userAction = useRef(false);

  // A tap/click pick: reveal the claim button if it sits below the fold (no-op when visible). The
  // landing pages' programmatic preselect calls setPicked directly, so a page load never moves the
  // viewport — only a real tap/click does. Arrow-key picks don't scroll either (`selectQuietly`):
  // yanking the page to the button would carry the focused card out of view.
  const pickAndReveal = useCallback((loc: string) => {
    setPicked(loc);
    setNotice(null);
    requestAnimationFrame(() => revealNearest(ctaRef.current));
  }, []);
  const selectQuietly = useCallback((loc: string) => {
    setPicked(loc);
    setNotice(null);
  }, []);

  // After a claim resolves, the widget re-renders into a (usually shorter) outcome card while the
  // browser keeps the old scroll offset — leaving the user staring below it. Once the new view has
  // PAINTED (double rAF), bring the card's top back under the sticky header — but only when it
  // isn't already in view, so desktop layouts never jump. Focus moves to the outcome's HEADING
  // (without a second scroll): a screen reader announces the title, not an unnamed box.
  useEffect(() => {
    if (!outcomeSeq) return;
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        const el = rootRef.current;
        userAction.current = false;
        if (!el) return;
        const top = el.getBoundingClientRect().top;
        const headerEdge =
          (document.querySelector("header.hd")?.getBoundingClientRect().height ?? 64) + 8;
        if (top < headerEdge - 4 || top > window.innerHeight * 0.6) {
          el.scrollIntoView({ block: "start", behavior: scrollBehavior() });
        }
        (el.querySelector<HTMLElement>("h2") ?? el).focus({ preventScroll: true });
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [outcomeSeq]);

  // The server is authoritative once loaded: if it reports no config (e.g. after a device reset),
  // drop any stale optimistic claim result so we don't keep showing a revoked config. And watch for
  // the growth moment: a config that was out of volume and now isn't has just been revived.
  const prevStatus = useRef<StatusResponse | null>(null);
  useEffect(() => {
    if (!status) return;
    const prev = prevStatus.current;
    if (!status.has_config) {
      setResult(null);
      setRevived(null);
    } else if (prev?.has_config && prev.data_exhausted && !status.data_exhausted) {
      setRevived({
        friend: status.referral_count > prev.referral_count,
        addedBytes: Math.max(0, status.daily_limit_bytes - prev.daily_limit_bytes),
      });
    }
    prevStatus.current = status;
  }, [status]);

  // Apply `preselect` once the live location list is in — ONCE per value, so a manual choice made
  // after it wins, and a list refresh does not undo that choice. A NEW value does apply over an
  // earlier pick: on the homepage it is `?loc=`, and tapping another flag on the same page changes it
  // without remounting the widget — that tap is the newer intent. Matches by exact remark or
  // normalized display name (the same tolerance as the "popular" star in the Picker).
  const appliedPreselect = useRef<string | null>(null);
  useEffect(() => {
    if (!preselect || !locs.length || appliedPreselect.current === preselect) return;
    appliedPreselect.current = preselect;
    const hit = locs.find((l) => sameLoc(l, preselect));
    if (hit) {
      setPicked(hit);
      setNotice(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locations, preselect]);

  // A landing page promises a SPECIFIC location (preselect). If that remark no longer matches any
  // live location (panel rename), fall through to "no selection" — NOT the popular default — so the
  // page never silently claims a different country than the one it advertised. The user picks.
  const preselectMiss = !!preselect && locs.length > 0 && !locs.some((l) => sameLoc(l, preselect));
  // Switching needs an explicit choice — defaulting to the popular card would offer to "switch" to
  // the location already in use.
  const selected = changeLoc
    ? picked
    : (picked ?? (preselectMiss ? null : defaultPick) ?? (compact && locs.length ? locs[0] : null));

  const doClaim = useCallback(async () => {
    if (!selected || mode === "provisioning") return;
    userAction.current = true;
    setMode("provisioning");
    setErrState(false);
    setNotice(null);
    let settled = true; // false only while the automatic 429 retry is pending
    try {
      // the views the outcome will need are fetched alongside, so the outcome is never held up by them
      const [res] = await Promise.all([api.claim(selected, token || undefined), loadAfter().catch(() => null)]);
      clearToken(); // single-use token: clear it AND reset the widget for the next claim
      if (res.reason !== "rate_limited") retried.current = false;
      if (res.ok) {
        setResult(res);
        setChangeLoc(false);
        setPicked(null);
        setRevived(null); // a new delivery is its own news; the revive has been told
        await reload();
      } else {
        switch (res.reason) {
          case "cooldown":
            await reload(); // S5, counting down to the instant the server named
            break;
          case "blocked":
            // Blocked while this tab sat on the picker: the fresh status says so (SB), where a
            // generic error screen would invite a retry that can never succeed.
            await reload();
            break;
          case "location_unavailable":
            // The squad stopped serving what we offered (renamed/disabled host, or a tab left open).
            // Re-sync the picker and say so in place — the server deliberately refuses to
            // substitute a different country, and a full error page made the user find the picker
            // again for nothing.
            setPicked(null);
            await refreshLocations();
            setNotice("loc_gone");
            break;
          case "not_ready":
          case "no_locations":
            // Nothing is wrong with the visitor's claim: there is simply nothing to hand out yet.
            await refreshLocations();
            setUnavailable(true);
            break;
          case "rate_limited":
            // Almost always our own single-flight lock — a double tap or a second tab whose claim
            // is still provisioning. Keep the button busy and try once more by ourselves; if that
            // is refused too, show whatever the other request produced, with a note.
            if (!retried.current) {
              retried.current = true;
              settled = false;
              setRetryPending(true);
            } else {
              retried.current = false;
              await reload();
              setNotice("busy");
            }
            break;
          case "turnstile_failed":
            setNotice("ts"); // clearToken() above already asked Cloudflare for a fresh token
            break;
          default:
            setErrState(true); // panel_error / an unexpected guard: the genuine S8
        }
      }
    } catch {
      setErrState(true);
    } finally {
      setMode("idle");
      if (settled) setOutcomeSeq((s) => s + 1); // re-rendered into an outcome — snap back to it
    }
  }, [selected, token, mode, reload, clearToken, refreshLocations]);

  // The automatic retry after a 429: ~1.5s later, and only once a fresh Turnstile token exists (the
  // refused request may already have spent the old one). A Turnstile failure abandons it.
  useEffect(() => {
    if (!retryPending) return;
    if (tsError) {
      setRetryPending(false);
      retried.current = false;
      return;
    }
    if (needsTurnstile && !token) return;
    const id = window.setTimeout(() => {
      setRetryPending(false);
      void doClaim();
    }, 1500);
    return () => window.clearTimeout(id);
  }, [retryPending, tsError, needsTurnstile, token, doClaim]);

  // ---- derive the display state from the live status (status wins; result is the pre-reload view) ----
  const serverHasConfig = !!status?.has_config;
  const link = serverHasConfig ? (status?.link ?? null) : result?.ok ? (result.link ?? null) : null;
  const hasConfig = serverHasConfig || (!!result?.ok && !!result.link);
  // Just provisioned this session → celebrate (S3). A change-location claim returns changed=true;
  // that's the calm returning view (S4), not a fresh-claim celebration.
  const fresh = !!result?.ok && !result.changed;
  const exhausted = !!status?.data_exhausted;
  const canClaim = status?.can_claim ?? true;
  // The operator blocked this device: it gets nothing, whatever its cooldown says, so it is neither
  // a cooldown to count down nor one to poll for.
  const blocked = status?.status === "blocked";

  // The last config this browser was shown, kept for when the network is gone (lib/lastConfig): the
  // offline page hands it back, and so does S8 below when /status cannot be reached — offline, the
  // service worker serves the cached home and status pages too, not only /offline. Only what the
  // SERVER confirmed moves it: a live config is saved, "none" (ended, reset, blocked) clears it, and
  // an unreachable server changes nothing.
  useEffect(() => {
    if (loading || offline || !status) return;
    saveLastConfig(
      serverHasConfig && status.link
        ? {
            link: status.link,
            location: status.location ?? null,
            label: status.location ? locLabel(status.location, locale) : null,
            expires_at: status.expires_at ?? null,
          }
        : null,
    );
  }, [loading, offline, status, serverHasConfig, locale]);
  const [saved, setSaved] = useState<LastConfig | null>(null);
  useEffect(() => {
    if (offline) setSaved(readLastConfig());
  }, [offline]);
  const pct =
    status && status.daily_limit_bytes > 0
      ? Math.round((status.usage_bytes / status.daily_limit_bytes) * 100)
      : 0;

  // Absolute deadlines on this device's clock (lib/time corrects for a wrong phone clock), and what
  // happens when they pass: ask the server — right away, then backing off — until it reports the
  // consequence (the cooldown lifted, the config ended). The old countdown ran from a string
  // rounded to the minute: under a minute it read "0m", hit zero at once, reloaded, got "0m" again
  // and sat on 00:00:00 until the visitor refreshed by hand.
  const cooldownAt = status
    ? clientDeadline(status.cooldown_until, status.server_time, statusAt, status.cooldown)
    : null;
  const expiresAt = status
    ? clientDeadline(status.expires_at, status.server_time, statusAt, status.remaining)
    : null;
  const inCooldown = !loading && !hasConfig && !canClaim && !blocked;
  const cooldownOver = useExpired(inCooldown ? cooldownAt : null);
  useBackoffPoll(inCooldown && cooldownOver, poll);
  const configOver = useExpired(hasConfig ? expiresAt : null);
  useBackoffPoll(!loading && hasConfig && configOver, poll);
  // S6 waits on someone ELSE (a friend's first claim revives this config): check every 25s while
  // the tab is visible, and the moment it becomes visible again.
  useVisiblePoll(!loading && hasConfig && exhausted, poll);

  // ---- which screen, and what it is called (the live region announces changes nobody tapped for) ----
  const view: string = loading
    ? "loading"
    : offline || errState
      ? "s8"
      : blocked
        ? "sb"
        : unavailable
          ? "s7x"
          : hasConfig && exhausted
            ? "s6"
            : hasConfig && link
              ? revived
                ? "rv"
                : fresh
                  ? "s3"
                  : "s4"
              : !canClaim
                ? "s5"
                : locs.length === 0
                  ? "s7"
                  : "s1";
  const viewTitle: Record<string, string> = {
    s8: t("err_title"),
    sb: t("blk_title"),
    s7x: t("empty_title"),
    s7: t("empty_title"),
    s6: t("ex_title"),
    rv: t("revived_title"),
    s3: t("succ_title"),
    s4: t("active_title"),
    s5: t("cd_title"),
    s1: t("w_title"),
  };
  const [announce, setAnnounce] = useState("");
  const prevView = useRef<string | null>(null);
  useEffect(() => {
    const before = prevView.current;
    prevView.current = view;
    if (before === null || before === "loading" || before === view) return;
    // A tapped claim's outcome is announced by moving focus to its heading; everything else — a
    // cooldown running out, a friend reviving the config — happens with nobody's hand on the
    // widget and has to be SAID.
    if (!userAction.current) setAnnounce(viewTitle[view] ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  // The post-claim views are drawn from `widget/after` (see loadAfter): until it is here they show the
  // loading skeleton. S8 only offers the saved config with it, so it never waits — offline, the
  // fetch may not succeed at all.
  const postClaim = view === "s3" || view === "s4" || view === "rv" || view === "s5" || view === "s6";
  const after = useAfter(postClaim || (view === "s8" && offline && !!saved));
  const drawn = postClaim && !after ? "loading" : view;
  useEffect(() => {
    if (readLastConfig()) void loadAfter().catch(() => {});
  }, []);

  const busy = mode === "provisioning" || retryPending;
  const ctaProps = {
    locale,
    busy,
    onClaim: doClaim,
    needsTurnstile,
    token,
    siteKey: config?.turnstile_site_key ?? "",
    onToken: setToken,
    onTsError,
    onTsRetry: retryTurnstile,
    tsError,
    tsReset,
    notice,
  };

  let body: ReactNode;

  // ---------- loading ----------
  if (drawn === "loading") {
    body = (
      // Skeleton mirrors the S1 picker's shape (title · location grid · CTA) so it fills the
      // reserved widget height — the resolve into the real picker doesn't visibly jump.
      // The key makes the resolve a REPLACEMENT: without it React recycles the skeleton's divs
      // (the grid placeholder became S1's `.cta-anchor`), and a recycled node that moves is a
      // layout shift — 0.13 CLS on a phone once the skeleton actually painted.
      <div className="widget wskel" aria-busy key="loading" data-view="loading">
        <div className="skeleton" style={{ height: 40, width: "55%", marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 18, width: "72%", marginBottom: 18 }} />
        <div className="skeleton wskel-grid" style={{ marginBottom: 16 }} />
        <div className="skeleton" style={{ height: 52 }} />
      </div>
    );
  }

  // ---------- S8 panel error ----------
  else if (drawn === "s8") {
    body = (
      <div className="widget is-short" ref={rootRef} tabIndex={-1} data-view={view}>
        <CenterState kind="err" title={t("err_title")} sub={t("err_sub")}>
          <button
            className="btn"
            onClick={() => {
              setErrState(false);
              void reload();
            }}
          >
            {t("err_retry")}
          </button>
          <Link className="btn ghost" href="/faq">
            {t("err_help")}
          </Link>
        </CenterState>
        {offline && saved && after && <after.SavedConfig locale={locale} config={saved} />}
      </div>
    );
  }

  // ---------- S7 at claim time: nothing to hand out yet (not_ready / no_locations) ----------
  else if (drawn === "s7x") {
    body = (
      <div className="widget is-short" ref={rootRef} tabIndex={-1} data-view={view}>
        <CenterState kind="empty" title={t("empty_title")} sub={t("empty_sub")}>
          <button
            className="btn"
            onClick={() => {
              setUnavailable(false);
              void refreshLocations();
              void reload();
            }}
          >
            {t("err_retry")}
          </button>
          <Link className="btn ghost" href="/faq">
            {t("empty_link")}
          </Link>
        </CenterState>
      </div>
    );
  }

  // ---------- S6 revive (data exhausted) ----------
  else if (drawn === "s6" && after) {
    body = (
      <div className="widget is-short" ref={rootRef} tabIndex={-1} data-view={view}>
        <StatusHead kind="warn" title={t("ex_title")} sub={t("ex_sub")} />
        <after.UsageMeter
          usedBytes={status?.usage_bytes ?? null}
          totalBytes={status?.daily_limit_bytes ?? null}
          pct={100}
          locale={locale}
        />
        <after.ReviveBlock
          locale={locale}
          refCode={status?.ref_code ?? ""}
          rewardMb={config?.reward_referral_mb}
        />
      </div>
    );
  }

  // ---------- S3/S4 delivered config (and its revived variant) ----------
  else if ((drawn === "rv" || drawn === "s3" || drawn === "s4") && after) {
    const loc = (fresh ? result?.location : status?.location) ?? status?.location ?? "";
    const head =
      view === "rv"
        ? { title: t("revived_title"), sub: t("revived_sub") }
        : view === "s3"
          ? { title: `${t("succ_title")} 🎉`, sub: t("succ_sub") }
          : { title: t("active_title"), sub: t("active_sub") };
    const switchTo = selected && !sameLoc(selected, current) ? selected : null;
    body = (
      <div className="widget" ref={rootRef} tabIndex={-1} data-view={view}>
        <div className="cfg">
          <StatusHead kind="ok" title={head.title} sub={head.sub} />
          {view === "rv" && revived && <RevivedNote locale={locale} revived={revived} />}
          {loc && (
            <div className="cfg-loc">
              <Flag name={loc} size={34} eager />
              <span className="nm">{locLabel(loc, locale)}</span>
              <span className="ok">
                <Icon name="check" sw={2.6} /> {t("ready")}
              </span>
            </div>
          )}
          <span className="field-label">{t("link_label")}</span>
          <after.CopyField value={link ?? ""} locale={locale} />
          <after.AppButtons link={link ?? ""} locale={locale} />
          {link && <after.QrToggle value={link} locale={locale} />}
          <after.UsageMeter
            usedBytes={status?.usage_bytes ?? 0}
            totalBytes={status?.daily_limit_bytes ?? null}
            pct={pct}
            locale={locale}
            remainingBytes={status ? Math.max(0, status.daily_limit_bytes - status.usage_bytes) : 0}
            // only a LIVE zero is "nothing used" — with the panel unreachable usage_bytes is 0 too
            note={status?.live && status.usage_bytes <= 0 ? t("usage_none") : undefined}
          />
          {expiresAt != null && (
            <>
              <hr className="divider" />
              <after.Countdown deadline={expiresAt} label={t("time_left")} locale={locale} />
            </>
          )}
          {changeLoc ? (
            <div ref={changePickRef} className="pick-anchor">
              <Picker
                locale={locale}
                locations={locs}
                selected={selected}
                onPick={pickAndReveal}
                onSelect={selectQuietly}
                disabled={busy}
                popular={popular}
                current={current}
              />
              <div ref={ctaRef} className="cta-anchor">
                <CtaBlock
                  {...ctaProps}
                  disabled={!switchTo}
                  label={(switchTo && fill(t("change_to"), { loc: locLabel(switchTo, locale) })) || t("change_pick")}
                  onCancel={() => {
                    setChangeLoc(false);
                    setPicked(null);
                    setNotice(null);
                  }}
                />
              </div>
            </div>
          ) : (
            /* change-location as an inviting list row: rotating swap chip, label + the REAL count
               of alternative locations, trailing chevron — not just a flat outline button */
            <button
              className="chg-btn"
              onClick={() => {
                setChangeLoc(true);
                setPicked(null);
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
                  <small>{faDigits(fill(t("chg_more"), { n: locs.length - 1 }) ?? "", locale)}</small>
                )}
              </span>
              <Icon name="chevr" sw={2.4} cls="ic-dir chg-chev" />
            </button>
          )}
          {view === "s3" && !changeLoc && <after.Missions locale={locale} refCode={status?.ref_code ?? ""} />}
        </div>
      </div>
    );
  }

  // ---------- SB blocked by the operator ----------
  else if (drawn === "sb") {
    body = (
      <div className="widget is-short" ref={rootRef} tabIndex={-1} data-view={view}>
        <CenterState kind="err" title={t("blk_title")} sub={t("blk_sub")}>
          <Link className="btn secondary" href="/contact">
            {t("blk_contact")}
          </Link>
        </CenterState>
      </div>
    );
  }

  // ---------- S5 cooldown ----------
  else if (drawn === "s5" && after) {
    body = (
      <div className="widget is-short" ref={rootRef} tabIndex={-1} data-view={view}>
        <StatusHead kind="wait" title={t("cd_title")} sub={t("cd_sub")} />
        {cooldownAt != null && (
          <div style={{ paddingBlock: 6 }}>
            <after.Countdown deadline={cooldownAt} label={t("cd_next")} locale={locale} />
          </div>
        )}
        <after.Missions locale={locale} refCode={status?.ref_code ?? ""} />
      </div>
    );
  }

  // ---------- S7 no locations ----------
  else if (drawn === "s7") {
    body = (
      <div className="widget is-short" ref={rootRef} tabIndex={-1} data-view={view}>
        <CenterState kind="empty" title={t("empty_title")} sub={t("empty_sub")}>
          <Link className="btn secondary" href="/faq">
            {t("empty_link")}
          </Link>
        </CenterState>
      </div>
    );
  }

  // ---------- S1 idle (+ S2 provisioning overlay) ----------
  else {
    body = (
      <div className="widget" ref={rootRef} tabIndex={-1} data-view={view}>
        <RefWelcome locale={locale} status={status} />
        <WidgetHead
          locale={locale}
          title={title ?? t("w_title")}
          sub={compact ? null : t("w_sub")}
          allowance={
            status && status.daily_limit_bytes > 0
              ? formatVolume(status.daily_limit_bytes, locale)
              : undefined
          }
        />
        <Picker
          locale={locale}
          locations={locs}
          selected={selected}
          onPick={pickAndReveal}
          onSelect={selectQuietly}
          disabled={busy}
          popular={popular}
        />
        <div ref={ctaRef} className="cta-anchor">
          <CtaBlock
            {...ctaProps}
            disabled={!selected}
            label={t("cta_get")}
            trialHours={config?.trial_hours ?? status?.trial_hours}
          />
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Mounted for the widget's whole life, outside the per-state roots: a live region inserted
          together with its text is not announced. */}
      <p className="sr-only" role="status" aria-live="polite">
        {announce}
      </p>
      {body}
    </>
  );
}

// ================= sub-parts =================

// The title and subtitle arrive resolved, so the panel's overrides (w_title / w_sub) reach them —
// a translator built here from the locale alone never saw those.
function WidgetHead({
  locale,
  title,
  sub,
  allowance,
}: {
  locale: Locale;
  title: string;
  sub: string | null;
  allowance?: string;
}) {
  const t = useT();
  const chip = allowance ? fill(t("allowance"), { v: allowance }) : null;
  return (
    <div className="w-head">
      <span className="w-badge" aria-hidden>
        <Icon name="bolt" sw={2.2} />
      </span>
      <div className="wt">
        <h2 className="w-title" tabIndex={-1}>
          {title}
        </h2>
        {sub && <p className="w-sub">{sub}</p>}
      </div>
      {chip && (
        <span className="allowance">
          <Icon name="bolt" sw={2} /> {faDigits(chip, locale)}
        </span>
      )}
    </div>
  );
}

// A visitor who arrived through a friend's invite link is told so — and that their first claim is
// what credits the friend. A device that has claimed before, or its own link, gets nothing.
function RefWelcome({ locale, status }: { locale: Locale; status: StatusResponse | null }) {
  const t = useT();
  const [ref] = useState(() =>
    typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("ref") : null,
  );
  if (!ref || !status || status.configs > 0 || ref === status.ref_code) return null;
  return (
    <div className="ref-welcome">
      <Icon name="gift" sw={2} />
      <span>{t("ref_welcome")}</span>
    </div>
  );
}

// The location grid as a REAL radio group: one Tab stop (the checked card, else the first), arrows
// move the choice — flipped for the reading direction — and Home/End jump to the ends. Before, all
// 22 cards were Tab stops, so a keyboard reached the claim button after 27 presses. And it shows two
// rows plus "all locations (22)" instead of a nested scroll box, which trapped a thumb on a phone:
// the grid scrolled, and at its end the page did not move.
function Picker({
  locale,
  locations,
  selected,
  onPick,
  onSelect,
  disabled,
  popular,
  current,
}: {
  locale: Locale;
  locations: string[];
  selected: string | null;
  onPick: (v: string) => void;
  onSelect: (v: string) => void;
  disabled?: boolean;
  popular?: string | null;
  /** In change-location mode: the location in use, marked «فعلی». */
  current?: string | null;
}) {
  const t = useT();
  const labelId = useId();
  const gridRef = useRef<HTMLDivElement>(null);
  const [all, setAll] = useState(false);
  const cols = useGridColumns();
  const limit = cols * 2;
  const collapsed = !all && locations.length > limit;
  const checkedIndex = locations.findIndex((l) => l === selected);
  const tabIndexOf = (i: number) => (i === (checkedIndex >= 0 ? checkedIndex : 0) ? 0 : -1);

  function onKeyDown(e: React.KeyboardEvent, i: number) {
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const step: Record<string, number> = {
      ArrowDown: 1,
      ArrowUp: -1,
      ArrowRight: rtl ? -1 : 1,
      ArrowLeft: rtl ? 1 : -1,
    };
    let next: number;
    if (e.key in step) next = (i + step[e.key] + locations.length) % locations.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = locations.length - 1;
    else return;
    e.preventDefault();
    onSelect(locations[next]);
    const card = gridRef.current?.querySelectorAll<HTMLButtonElement>(".loc-card")[next];
    if (card && !card.hidden) {
      card.focus(); // at once: the checked radio and the focused one never disagree
    } else {
      setAll(true); // arrowing past the two rows opens the rest — focus once they render
      requestAnimationFrame(() => {
        gridRef.current?.querySelectorAll<HTMLButtonElement>(".loc-card")[next]?.focus();
      });
    }
  }

  return (
    <>
      <div className="pick-label">
        <span className="l" id={labelId}>
          {t("pick")}
        </span>
        <span className="c tnum">{faDigits(fill(t("pick_count"), { n: locations.length }) ?? "", locale)}</span>
      </div>
      <div
        ref={gridRef}
        className="loc-grid"
        role="radiogroup"
        aria-labelledby={labelId}
        aria-disabled={disabled || undefined}
        style={disabled ? { opacity: 0.55, pointerEvents: "none" } : undefined}
      >
        {locations.map((loc, i) => {
          const on = selected === loc;
          // Badges are matched by remark NAME (never index). «فعلی» wins over «محبوب»: when
          // switching, where you ARE matters more than what is popular.
          const isCurrent = sameLoc(loc, current);
          const isPopular = !isCurrent && sameLoc(loc, popular);
          return (
            <button
              key={loc}
              type="button"
              className="loc-card"
              role="radio"
              aria-checked={on}
              tabIndex={tabIndexOf(i)}
              hidden={collapsed && i >= limit}
              disabled={disabled}
              onClick={() => onPick(loc)}
              onKeyDown={(e) => onKeyDown(e, i)}
            >
              {isPopular && (
                <span className="loc-rec">
                  <svg className="ic" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M12 2.6l2.7 5.5 6 .9-4.35 4.24 1.03 6L12 16.9l-5.38 2.84 1.03-6L3.3 9l6-.9z" />
                  </svg>
                  {t("rec")}
                </span>
              )}
              {isCurrent && <span className="loc-rec loc-now">{t("loc_current")}</span>}
              <span className="loc-check" aria-hidden>
                <Icon name="check" sw={2.6} />
              </span>
              {/* sized by CSS (smaller on a phone); no green "online" dot — every card had one,
                  so it said nothing about any of them */}
              <Flag name={loc} fluid eager={i < limit} />
              <span className="nm">{locLabel(loc, locale)}</span>
            </button>
          );
        })}
      </div>
      {collapsed && (
        <button
          type="button"
          className="loc-more"
          onClick={() => {
            setAll(true);
            // the button disappears with the rows it revealed — hand focus to the first of them
            requestAnimationFrame(() => {
              gridRef.current?.querySelectorAll<HTMLButtonElement>(".loc-card")[limit]?.focus();
            });
          }}
        >
          {faDigits(fill(t("loc_more_all"), { n: locations.length }) ?? "", locale)}
          <Icon name="chev" sw={2.4} />
        </button>
      )}
    </>
  );
}

/** The grid's column count — the same 520px breakpoint styles/base.css switches it at. */
function useGridColumns(): number {
  const query = "(min-width:520px)";
  const [cols, setCols] = useState(() =>
    typeof window !== "undefined" && window.matchMedia(query).matches ? 4 : 3,
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const sync = () => setCols(mq.matches ? 4 : 3);
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return cols;
}

function CtaBlock({
  locale,
  label,
  disabled,
  busy,
  onClaim,
  onCancel,
  needsTurnstile,
  token,
  siteKey,
  onToken,
  onTsError,
  onTsRetry,
  tsError,
  tsReset,
  trialHours,
  notice,
}: {
  locale: Locale;
  label: string;
  disabled: boolean;
  busy: boolean;
  onClaim: () => void;
  /** Present in change-location mode: a way back that does not claim anything. */
  onCancel?: () => void;
  needsTurnstile: boolean;
  token: string;
  siteKey: string;
  onToken: (t: string) => void;
  onTsError: () => void;
  onTsRetry: () => void;
  tsError: boolean;
  tsReset: number;
  trialHours?: number;
  notice: Notice;
}) {
  const t = useT();
  const switching = !!onCancel;
  // the renewal window is the operator's setting — unknown means say nothing, never a guessed 24
  const renew = fill(t("reassure3"), { h: trialHours });
  const reassure3 = renew && faDigits(renew, locale);
  // Before a token exists the button cannot work — say why instead of sitting there disabled (on a
  // slow network the Turnstile script takes seconds, and a silent grey button reads as broken).
  const verifying = needsTurnstile && !token && !tsError && !busy;
  // A slow panel: after 3s the label admits it is taking longer, so the wait reads as progress.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!busy) {
      setSlow(false);
      return;
    }
    const id = window.setTimeout(() => setSlow(true), 3000);
    return () => window.clearTimeout(id);
  }, [busy]);

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
      {notice && (
        <div className="w-notice" role="alert" data-notice={notice}>
          <Icon name="warn" sw={2} />
          <span>{t(`notice_${notice}`)}</span>
        </div>
      )}
      <button
        className="btn cta"
        disabled={disabled || busy || verifying || (needsTurnstile && !token)}
        aria-busy={busy || verifying}
        onClick={onClaim}
      >
        {busy || verifying ? (
          <>
            <span className="spinner" /> {verifying ? t("cta_verifying") : slow ? t("cta_slow") : t("cta_prep")}
          </>
        ) : switching ? (
          <>
            <Icon name="swap" sw={2.2} />
            {label}
          </>
        ) : (
          <>
            <Icon name="bolt" sw={2.2} />
            {label}
            <Icon name="arrow" sw={2.4} cls="ic-dir" />
          </>
        )}
      </button>
      {switching ? (
        <button type="button" className="btn ghost block chg-cancel" onClick={onCancel}>
          {t("chg_cancel")}
        </button>
      ) : (
        // The reassurances sell a FIRST claim; to someone already holding a config and only
        // switching its location they are noise.
        <>
          <div className="reassure">
            <span className="r">
              <Icon name="check" sw={2.6} /> {t("reassure1")}
            </span>
            <span className="r">
              <Icon name="check" sw={2.6} /> {t("reassure2")}
            </span>
            {reassure3 && (
              <span className="r">
                <Icon name="check" sw={2.6} /> {reassure3}
              </span>
            )}
          </div>
          <div className="antibot">
            <Icon name="shield" sw={2} /> {t("antibot")}
          </div>
        </>
      )}
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
        <h2 className="st-t" tabIndex={-1}>
          {title}
        </h2>
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
  children: ReactNode;
}) {
  return (
    <div className="center-state">
      <div className={`state-art ${kind}`} aria-hidden>
        <Icon name={kind === "empty" ? "globe" : "plug"} sw={1.9} />
      </div>
      <h2 className="ct" tabIndex={-1}>
        {title}
      </h2>
      <p className="cd2">{sub}</p>
      <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
        {children}
      </div>
    </div>
  );
}

// Why the config came back, and by how much — the growth loop's payoff, so it is spelled out.
function RevivedNote({ locale, revived }: { locale: Locale; revived: Revived }) {
  const t = useT();
  const amount = revived.addedBytes > 0 ? formatVolume(revived.addedBytes, locale) : null;
  const text = revived.friend
    ? amount
      ? fill(t("revived_friend"), { v: amount })
      : t("revived")
    : amount
      ? fill(t("reward_added"), { v: amount })
      : null;
  if (!text) return null;
  return (
    <div className="revived-note show">
      <Icon name="check" sw={2.6} />
      <span>{text}</span>
    </div>
  );
}
