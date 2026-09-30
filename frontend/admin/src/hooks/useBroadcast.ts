import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { stillInFlight } from "@/lib/inflight";
import type {
  ActivityHours,
  BroadcastAudience,
  BroadcastDraft,
  BroadcastDraftSave,
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

const LANG_ORDER: Lang[] = ["fa", "en", "ru"];

export function useAudience(languages: Lang[], filter: AudienceFilter = {}) {
  // In one fixed order: the SET is the audience, not the order it was ticked in — toggling fa off
  // and on gave "en,ru,fa", a second cache key and a second request for a count already on screen.
  const param = LANG_ORDER.filter((l) => languages.includes(l)).join(",");
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

/** Claims per local hour of day over the last 30 days — the composer's scheduling strip.
 *
 * Its own endpoint rather than the dashboard's analytics: the strip needs 24 numbers, and pulling
 * the whole analytics payload (and re-pulling it every minute) cost ~20 aggregate queries each time.
 * An hour-of-day profile over a month does not move while a message is being written. */
export function useActivityHours() {
  return useQuery({
    queryKey: ["broadcast-hours"],
    queryFn: async () => (await api.get<ActivityHours>("/admin/broadcast/hours")).data,
    staleTime: 10 * 60_000,
  });
}

/** Past broadcasts. Polled while one is in flight, so the row fills in without a reload — and,
 *  more slowly, while one is SCHEDULED: that row used to sit on «زمان‌بندی‌شده» until the page was
 *  reopened, long after it had gone out. */
export function useBroadcastHistory() {
  return useQuery({
    queryKey: ["broadcast-history"],
    queryFn: async () => (await api.get<BroadcastLog[]>("/admin/broadcast/history")).data,
    refetchInterval: (q) => {
      const rows = q.state.data ?? [];
      if (stillInFlight(rows)) return 5_000;
      if (rows.some((r) => r.status === "scheduled")) return 30_000;
      return false;
    },
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

/** Saved-but-unsent broadcasts. Server-side, not `localStorage`: the console is shared, so a draft
 *  one admin wrote has to be there for the one who sends it — and survive a cleared cache. */
export function useDrafts() {
  return useQuery({
    queryKey: ["broadcast-drafts"],
    queryFn: async () => (await api.get<BroadcastDraft[]>("/admin/broadcast/drafts")).data,
  });
}

export function useSaveDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BroadcastDraftSave) =>
      (await api.post<BroadcastDraft>("/admin/broadcast/drafts", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcast-drafts"] }),
  });
}

export function useDeleteDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/admin/broadcast/drafts/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcast-drafts"] }),
  });
}
