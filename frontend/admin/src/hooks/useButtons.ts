import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ButtonAppearancePatch, ButtonConfig, ReorderItem } from "@/types/api";

// Every mutation returns the full refreshed listing, so we just overwrite the cache.
export function useButtons() {
  return useQuery({
    queryKey: ["buttons"],
    queryFn: async () => (await api.get<ButtonConfig[]>("/admin/buttons/")).data,
  });
}

export function useUpdateButton() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, patch }: { key: string; patch: ButtonAppearancePatch }) =>
      (await api.put<ButtonConfig[]>(`/admin/buttons/${key}`, patch)).data,
    onSuccess: (data) => qc.setQueryData(["buttons"], data),
  });
}

export function useResetButton() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (key: string) =>
      (await api.post<ButtonConfig[]>(`/admin/buttons/${key}/reset`)).data,
    onSuccess: (data) => qc.setQueryData(["buttons"], data),
  });
}

export function useReorderButtons() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (items: ReorderItem[]) =>
      (await api.post<ButtonConfig[]>("/admin/buttons/reorder", { items })).data,
    onSuccess: (data) => qc.setQueryData(["buttons"], data),
  });
}
