"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type ClaimResponse } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";

function flag(name: string): string {
  const map: Record<string, string> = {
    germany: "🇩🇪", france: "🇫🇷", netherlands: "🇳🇱", uk: "🇬🇧", "united kingdom": "🇬🇧",
    usa: "🇺🇸", "united states": "🇺🇸", finland: "🇫🇮", sweden: "🇸🇪", turkey: "🇹🇷",
    poland: "🇵🇱", spain: "🇪🇸", italy: "🇮🇹", canada: "🇨🇦", japan: "🇯🇵", uae: "🇦🇪",
  };
  return map[name.trim().toLowerCase()] ?? "🌐";
}

export function ClaimWidget({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, config, loading, offline, reload, setStatus } = useSite();
  const [locations, setLocations] = useState<string[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [token, setToken] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ClaimResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.locations().then((r) => setLocations(r.locations)).catch(() => setLocations([]));
  }, []);

  // Seed the "already has a config" view from the loaded status.
  useEffect(() => {
    if (status?.has_config && status.link) {
      setResult((r) => r ?? { ok: true, link: status.link, location: status.location, expires: null, size: status.daily_limit, changed: false });
    }
  }, [status]);

  const needsTurnstile = !!config?.turnstile_enabled && !!config.turnstile_site_key;

  const doClaim = useCallback(async () => {
    if (!picked || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.claim(picked, token || undefined);
      if (res.ok) {
        setResult(res);
        await reload();
      } else {
        const reason = res.reason ?? "panel_error";
        if (reason === "cooldown") await reload();
        setError(t(`claim.${reason === "cooldown" ? "cooldownTitle" : reason === "not_ready" ? "notReady" : reason === "no_locations" ? "noLocations" : "panelError"}`));
      }
    } catch {
      setError(t("claim.panelError"));
    } finally {
      setBusy(false);
    }
  }, [picked, token, busy, reload, t]);

  async function copyLink() {
    if (!result?.link) return;
    try {
      await navigator.clipboard.writeText(result.link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked — ignore */
    }
  }

  if (loading) {
    return (
      <div className="card card-pad stack" aria-busy>
        <div className="skeleton" style={{ height: 22, width: "50%" }} />
        <div className="skeleton" style={{ height: 96 }} />
        <div className="skeleton" style={{ height: 48 }} />
      </div>
    );
  }

  // Cooldown state: claimed today, can't claim again yet.
  if (status && !status.can_claim && !result) {
    return (
      <div className="card card-pad stack center">
        <span className="chip chip-warning">{t("claim.cooldownTitle")}</span>
        <p className="lead">{t("claim.cooldownSub")}</p>
        <div className="code-lg tnum">{status.cooldown || "—"}</div>
        {status.link && (
          <a href={status.link} className="btn btn-ghost mt-4">
            {t("claim.copy")}
          </a>
        )}
      </div>
    );
  }

  // Delivered config.
  if (result?.link) {
    return (
      <div className="card card-pad stack">
        <div className="between">
          <span className="chip chip-success">✓ {result.location ?? status?.location}</span>
          {result.size && <span className="chip chip-muted">{t("claim.size")}: {result.size}</span>}
        </div>
        <div className="codebox">{result.link}</div>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={copyLink}>
            {copied ? t("claim.copied") : t("claim.copy")}
          </button>
          <button className="btn btn-ghost" onClick={() => setResult(null)}>
            {t("claim.changeLoc")}
          </button>
        </div>
        {result.expires && (
          <p className="hint">
            {t("claim.expires")}: <span className="tnum">{result.expires}</span>
          </p>
        )}
      </div>
    );
  }

  // Picker / claim.
  return (
    <div className="card card-pad stack">
      <div className="between">
        <strong>{t("claim.title")}</strong>
        {status && <span className="chip chip-muted">{t("claim.size")}: {status.daily_limit}</span>}
      </div>
      <p className="hint">{t("claim.pickLocation")}</p>
      {offline || locations.length === 0 ? (
        <p className="muted">{t("claim.noLocations")}</p>
      ) : (
        <div className="loc-grid">
          {locations.map((loc) => (
            <button
              key={loc}
              className="loc-card"
              aria-pressed={picked === loc}
              onClick={() => setPicked(loc)}
            >
              <span className="loc-flag" aria-hidden>{flag(loc)}</span>
              <span>{loc}</span>
            </button>
          ))}
        </div>
      )}
      {needsTurnstile && config && <Turnstile siteKey={config.turnstile_site_key} onToken={setToken} />}
      {error && <p className="err-text">{error}</p>}
      <button
        className="btn btn-primary btn-lg btn-block"
        disabled={!picked || busy || (needsTurnstile && !token)}
        onClick={doClaim}
      >
        {busy ? t("claim.loading") : t("claim.getBtn")}
      </button>
    </div>
  );
}
