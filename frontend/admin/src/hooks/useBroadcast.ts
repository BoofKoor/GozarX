import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  BroadcastAudience,
  BroadcastLog,
  BroadcastResult,
  BroadcastSend,
  Lang,
} from "@/types/api";

/** Live recipient count for the chosen language groups. ``languages`` is sent as a comma-separated
 *  query param (empty ⇒ everyone); the query key includes it so the count refetches on each change. */
export interface AudienceFilter {
  only_active?: boolean;
  only_referrers?: boolean;
}

export function useAudience(languages: Lang[], filter: AudienceFilter = {}) {
  const param = languages.join(",");
  const only_active = filter.only_active ?? false;
  const only_referrers = filter.only_referrers ?? false;
  return useQuery({
    queryKey: ["broadcast-audience", param, only_active, only_referrers],
    queryFn: async () =>
      (
        await api.get<BroadcastAudience>("/admin/broadcast/", {
          params: { languages: param, only_active, only_referrers },
        })
      ).data,
  });
}

/** Past broadcasts. Polled while one is in flight, so the row fills in without a reload. */
export function useBroadcastHistory() {
  return useQuery({
    queryKey: ["broadcast-history"],
    queryFn: async () => (await api.get<BroadcastLog[]>("/admin/broadcast/history")).data,
    refetchInterval: (q) =>
      (q.state.data ?? []).some((r) => r.status === "sending" || r.status === "queued")
        ? 5_000
        : false,
  });
}

export function useSendBroadcast() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BroadcastSend) =>
      (await api.post<BroadcastResult>("/admin/broadcast/", body)).data,
    // The new row exists the moment the request returns, so the history should show it queued
    // rather than waiting for the next poll.
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcast-history"] }),
  });
}
