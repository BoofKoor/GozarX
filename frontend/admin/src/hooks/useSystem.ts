import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { HealthSample, SystemHealth } from "@/types/api";

/** Live health snapshot.
 *
 * Polled once a minute by default — that is the top bar's dot, on every page. The System page,
 * whose whole job is the live reading, asks for 10s. Every poll used to cost a panel call and a
 * Telegram call regardless of which page was open; the server now shares those readings for 30s,
 * and this keeps an idle tab from asking six times a minute for a dot. */
export function useSystemHealth(intervalMs = 60_000) {
  return useQuery({
    queryKey: ["system-health"],
    queryFn: async () => (await api.get<SystemHealth>("/admin/system/health")).data,
    refetchInterval: intervalMs,
  });
}

/** Per-minute history samples (newest stored, returned oldest-first) for the trend charts. */
export function useSystemHistory(minutes: number) {
  return useQuery({
    queryKey: ["system-history", minutes],
    queryFn: async () =>
      (await api.get<HealthSample[]>("/admin/system/history", { params: { minutes } })).data,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
  });
}
