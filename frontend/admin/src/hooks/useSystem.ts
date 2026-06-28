import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { HealthSample, SystemHealth } from "@/types/api";

/** Live health snapshot — refetched every 10s (each call probes DB/Redis/panel/webhook). */
export function useSystemHealth() {
  return useQuery({
    queryKey: ["system-health"],
    queryFn: async () => (await api.get<SystemHealth>("/admin/system/health")).data,
    refetchInterval: 10_000,
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
