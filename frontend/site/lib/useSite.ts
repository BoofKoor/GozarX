"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type PublicConfig, type StatusResponse } from "@/lib/api";

export interface SiteState {
  status: StatusResponse | null;
  config: PublicConfig | null;
  loading: boolean;
  offline: boolean;
  reload: () => Promise<void>;
  setStatus: (s: StatusResponse) => void;
}

// One place to load the device's status + the public config. Status is device-scoped, so it is
// fetched in the browser (the httpOnly cookie round-trips). A network failure degrades to offline —
// never a thrown error — mirroring the backend's "status never errors" contract.
export function useSite(): SiteState {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.status(), api.config().catch(() => null)]);
      setStatus(s);
      if (c) setConfig(c);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { status, config, loading, offline, reload, setStatus };
}
