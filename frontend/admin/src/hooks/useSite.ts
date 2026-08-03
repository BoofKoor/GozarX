import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  SiteAnalytics,
  SiteDeviceAction,
  SiteDeviceCard,
  SiteDeviceListParams,
  SiteDevicePage,
  SiteDevicePeer,
  SiteDeviceRow,
  SiteCopyItem,
  SiteCopyPatch,
  SitePushLog,
  SetupStatus,
  SiteLandingInput,
  SiteLandingPage,
  SiteMessage,
  SiteMessagePage,
  SitePushAudience,
  SitePushInput,
  SitePushResult,
  SiteSettings,
  SiteSettingsPatch,
  SiteSetupPayload,
  SiteStats,
} from "@/types/api";

// Website ("site") admin section — settings + first-run wizard. Squad options reuse the bot's
// `useSquads()` (the same panel endpoint); nothing here touches the bot economy.

export function useSiteSettings() {
  return useQuery({
    queryKey: ["site-settings"],
    queryFn: async () => (await api.get<SiteSettings>("/admin/site/settings/")).data,
  });
}

export function useUpdateSiteSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: SiteSettingsPatch) =>
      (await api.put<SiteSettings>("/admin/site/settings/", patch)).data,
    onSuccess: (data) => qc.setQueryData(["site-settings"], data),
  });
}

export function useRefreshSiteLocations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      (await api.post<SiteSettings>("/admin/site/settings/refresh-locations")).data,
    onSuccess: (data) => qc.setQueryData(["site-settings"], data),
  });
}

export function useSiteDerivableLocations(squad: string) {
  return useQuery({
    queryKey: ["site-derivable-locations", squad],
    queryFn: async () =>
      (await api.get<string[]>("/admin/site/setup/locations", { params: { squad } })).data,
    enabled: Boolean(squad),
  });
}

export function useCompleteSiteSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SiteSetupPayload) =>
      (await api.post<SetupStatus>("/admin/site/setup/", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-setup-status"] });
      qc.invalidateQueries({ queryKey: ["site-settings"] });
    },
  });
}

// --- landing pages (CRUD) ---
export function useSiteLandingPages(locale?: string) {
  return useQuery({
    queryKey: ["site-pages", locale ?? "all"],
    queryFn: async () =>
      (await api.get<SiteLandingPage[]>("/admin/site/pages/", { params: locale ? { locale } : {} }))
        .data,
  });
}

export function useCreateLanding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SiteLandingInput) =>
      (await api.post<SiteLandingPage>("/admin/site/pages/", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-pages"] }),
  });
}

export function useUpdateLanding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: SiteLandingInput }) =>
      (await api.put<SiteLandingPage>(`/admin/site/pages/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-pages"] }),
  });
}

export function useDeleteLanding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/admin/site/pages/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-pages"] }),
  });
}

// --- contact inbox ---
export function useSiteMessages(page: number, unread: boolean, search?: string, locale?: string) {
  return useQuery({
    queryKey: ["site-messages", page, unread, search ?? "", locale ?? ""],
    queryFn: async () =>
      (
        await api.get<SiteMessagePage>("/admin/site/inbox/", {
          params: { page, unread, search: search || undefined, locale: locale || undefined },
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

/** Unread count for the tab badge — cheap, and shared with the list query's own `unread`. */
export function useSiteUnreadCount() {
  return useQuery({
    queryKey: ["site-messages-unread"],
    queryFn: async () =>
      (await api.get<SiteMessagePage>("/admin/site/inbox/", { params: { page: 1, unread: true } }))
        .data.unread,
    refetchInterval: 60_000,
  });
}

export function useMarkMessageUnread() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await api.post<SiteMessage>(`/admin/site/inbox/${id}/unread`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-messages"] });
      qc.invalidateQueries({ queryKey: ["site-messages-unread"] });
    },
  });
}

export function useDeleteMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/admin/site/inbox/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-messages"] });
      qc.invalidateQueries({ queryKey: ["site-messages-unread"] });
    },
  });
}

export function useMarkMessageRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await api.post<SiteMessage>(`/admin/site/inbox/${id}/read`)).data,
    // Optimistically flip the message to read IN PLACE rather than invalidating. A refetch in
    // unread-only mode would drop the just-opened message from the list before it could be read
    // (M1). This keeps it visible (now shown as read) and decrements the unread badge; on error we
    // roll every touched cache back. No onSettled refetch — that would re-introduce the vanish.
    onMutate: async (id: number) => {
      await qc.cancelQueries({ queryKey: ["site-messages"] });
      const prev = qc.getQueriesData<SiteMessagePage>({ queryKey: ["site-messages"] });
      const wasUnread = prev.some(([, d]) => d?.items.some((m) => m.id === id && !m.read));
      if (wasUnread) {
        qc.setQueriesData<SiteMessagePage>({ queryKey: ["site-messages"] }, (old) =>
          old
            ? {
                ...old,
                items: old.items.map((m) => (m.id === id ? { ...m, read: true } : m)),
                unread: Math.max(0, old.unread - 1),
              }
            : old,
        );
      }
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      ctx?.prev?.forEach(([key, data]) => qc.setQueryData(key, data));
    },
  });
}

// --- push broadcast ---
export function useSitePushAudience() {
  return useQuery({
    queryKey: ["site-push-audience"],
    queryFn: async () => (await api.get<SitePushAudience>("/admin/site/push/")).data,
  });
}

export function useSendSitePush() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SitePushInput) =>
      (await api.post<SitePushResult>("/admin/site/push/", body)).data,
    // Sending doesn't change the subscriber count, but it DOES add a history row — and that row is
    // the only place the admin ever learns what happened.
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-push-history"] }),
  });
}

// --- funnel stats ---
export function useSiteStats(days: number) {
  return useQuery({
    queryKey: ["site-stats", days],
    queryFn: async () =>
      (await api.get<SiteStats>("/admin/site/stats/", { params: { days } })).data,
    placeholderData: keepPreviousData, // keep the prior numbers while a new range loads
  });
}

/** Deeper website analytics (reward economy, streaks, push health, anti-abuse).
 *
 * Windowed by the SAME `days` the funnel above it uses. It used to ignore the range entirely, so
 * the page's 7/14/30 buttons moved the top half of the screen and silently did nothing to the
 * bottom half. Figures that are inherently lifetime are labelled as such in the UI. */
export function useSiteAnalytics(days: number) {
  return useQuery({
    queryKey: ["site-analytics", days],
    queryFn: async () =>
      (await api.get<SiteAnalytics>("/admin/site/stats/analytics", { params: { days } })).data,
    placeholderData: keepPreviousData,
  });
}

// --- website device browser (P4) ---
export function useSiteDevices(params: SiteDeviceListParams) {
  return useQuery({
    queryKey: ["site-devices", params],
    queryFn: async () => (await api.get<SiteDevicePage>("/admin/site/devices/", { params })).data,
    placeholderData: keepPreviousData, // keep the current page visible while the next loads
  });
}

export function useSiteDevice(uuid: string | null) {
  return useQuery({
    queryKey: ["site-device", uuid],
    queryFn: async () => (await api.get<SiteDeviceCard>(`/admin/site/devices/${uuid}`)).data,
    enabled: uuid != null,
  });
}

/** Devices sharing this one's browser fingerprint — the rows behind the anti-abuse count. */
export function useSiteDevicePeers(uuid: string | null) {
  return useQuery({
    queryKey: ["site-device-peers", uuid],
    queryFn: async () =>
      (await api.get<SiteDevicePeer[]>(`/admin/site/devices/${uuid}/peers`)).data,
    enabled: uuid != null,
  });
}

export function useSiteDeviceAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, action }: { uuid: string; action: SiteDeviceAction }) =>
      (await api.post<SiteDeviceRow>(`/admin/site/devices/${uuid}/${action}`)).data,
    onSuccess: (updated) => {
      qc.setQueryData(["site-device", updated.uuid], (old: SiteDeviceCard | undefined) =>
        old ? { ...old, ...updated } : old,
      );
      qc.invalidateQueries({ queryKey: ["site-devices"] });
      // Blocking/resetting shifts the status counts the site funnel shows.
      qc.invalidateQueries({ queryKey: ["site-stats"] });
    },
  });
}

// --- push history ---
/** Recent broadcasts and their outcome. Polled while anything is still in flight so a send that
 *  the worker is processing visibly finishes instead of sitting on "queued" forever. */
export function useSitePushHistory() {
  return useQuery({
    queryKey: ["site-push-history"],
    queryFn: async () => (await api.get<SitePushLog[]>("/admin/site/push/history")).data,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((r) => r.status === "queued" || r.status === "sending")
        ? 5_000
        : false,
  });
}

// --- website copy editor (P5) ---
export function useSiteCopy() {
  return useQuery({
    queryKey: ["site-copy"],
    queryFn: async () => (await api.get<SiteCopyItem[]>("/admin/site/content/")).data,
  });
}

export function useUpdateSiteCopy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, patch }: { key: string; patch: SiteCopyPatch }) =>
      (await api.put<SiteCopyItem>(`/admin/site/content/${key}`, patch)).data,
    onSuccess: (updated) =>
      qc.setQueryData(["site-copy"], (old: SiteCopyItem[] | undefined) =>
        old?.map((item) => (item.key === updated.key ? updated : item)),
      ),
  });
}
