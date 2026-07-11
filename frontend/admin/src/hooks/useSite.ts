import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
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
export function useSiteMessages(page: number, unread: boolean) {
  return useQuery({
    queryKey: ["site-messages", page, unread],
    queryFn: async () =>
      (await api.get<SiteMessagePage>("/admin/site/inbox/", { params: { page, unread } })).data,
    placeholderData: keepPreviousData,
  });
}

export function useMarkMessageRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await api.post<SiteMessage>(`/admin/site/inbox/${id}/read`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-messages"] }),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-push-audience"] }),
  });
}

// --- funnel stats ---
export function useSiteStats(days: number) {
  return useQuery({
    queryKey: ["site-stats", days],
    queryFn: async () =>
      (await api.get<SiteStats>("/admin/site/stats/", { params: { days } })).data,
  });
}
