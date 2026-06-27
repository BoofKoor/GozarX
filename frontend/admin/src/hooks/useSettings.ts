import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { EconomicsSettings, SettingsPatch } from "@/types/api";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => (await api.get<EconomicsSettings>("/admin/settings/")).data,
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: SettingsPatch) =>
      (await api.put<EconomicsSettings>("/admin/settings/", patch)).data,
    onSuccess: (data) => qc.setQueryData(["settings"], data),
  });
}
