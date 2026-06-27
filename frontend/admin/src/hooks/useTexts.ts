import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { BotText, TextPatch, TextPreview } from "@/types/api";

export function useTexts() {
  return useQuery({
    queryKey: ["texts"],
    queryFn: async () => (await api.get<BotText[]>("/admin/texts/")).data,
  });
}

export function useUpdateText() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, patch }: { key: string; patch: TextPatch }) =>
      (await api.put<BotText>(`/admin/texts/${key}`, patch)).data,
    onSuccess: (updated) =>
      qc.setQueryData<BotText[]>(["texts"], (prev) =>
        prev ? prev.map((t) => (t.key === updated.key ? updated : t)) : prev,
      ),
  });
}

export async function previewText(
  body: string,
  sample: Record<string, string>,
): Promise<TextPreview> {
  return (await api.post<TextPreview>("/admin/texts/preview", { body, sample })).data;
}
