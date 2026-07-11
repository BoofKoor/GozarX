import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { SetupStatus, SiteSettings, SiteSettingsPatch, SiteSetupPayload } from "@/types/api";

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
