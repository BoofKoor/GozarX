"use client";

import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, type PublicConfig, type StatusResponse } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export interface SiteState {
  locale: Locale;
  status: StatusResponse | null;
  config: PublicConfig | null;
  locations: string[] | null;
  loading: boolean;
  offline: boolean;
  reload: () => Promise<void>;
  refreshLocations: () => Promise<void>;
}

const SiteContext = createContext<SiteState | null>(null);

// ONE provider for the whole app (mounted in the root layout), so every component shares a SINGLE
// device-status/config/locations load instead of each fetching its own. Two things this fixes:
//   - the first-visit device-mint RACE: /status and /locations both mint a device when no cookie
//     exists; firing them in parallel from separate hooks minted several competing identities. Here
//     /status is awaited FIRST (it mints + Set-Cookie), then /config + /locations carry that cookie.
//   - stale state: a claim's reload() now updates the one shared status, so every stat re-renders.
export function SiteProvider({ locale, children }: { locale: Locale; children: ReactNode }) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [locations, setLocations] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const started = useRef(false);

  const loadLocations = useCallback(async () => {
    try {
      setLocations((await api.locations()).locations);
    } catch {
      setLocations([]);
    }
  }, []);

  const reload = useCallback(async () => {
    try {
      setStatus(await api.status());
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  const bootstrap = useCallback(async () => {
    try {
      // /status FIRST: it mints the device + sets the cookie. Awaiting it means the device exists
      // (exactly once) before anything else that also resolves the device runs.
      setStatus(await api.status());
      setOffline(false);
    } catch {
      setOffline(true);
    }
    // config is device-independent; locations now carry the freshly-set cookie (same device).
    await Promise.all([
      api
        .config()
        .then(setConfig)
        .catch(() => {}),
      loadLocations(),
    ]);
    setLoading(false);
  }, [loadLocations]);

  useEffect(() => {
    if (started.current) return; // guard against StrictMode double-invoke (would mint twice)
    started.current = true;
    void bootstrap();
  }, [bootstrap]);

  const value: SiteState = {
    locale,
    status,
    config,
    locations,
    loading,
    offline,
    reload,
    refreshLocations: loadLocations,
  };
  return createElement(SiteContext.Provider, { value }, children);
}

export function useSite(): SiteState {
  const ctx = useContext(SiteContext);
  if (ctx === null) {
    throw new Error("useSite must be used inside <SiteProvider>");
  }
  return ctx;
}
