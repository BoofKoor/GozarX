import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { BroadcastAudience, BroadcastResult } from "@/types/api";

export function useAudience() {
  return useQuery({
    queryKey: ["broadcast-audience"],
    queryFn: async () => (await api.get<BroadcastAudience>("/admin/broadcast/")).data,
  });
}

export function useSendBroadcast() {
  return useMutation({
    mutationFn: async (text: string) =>
      (await api.post<BroadcastResult>("/admin/broadcast/", { text })).data,
  });
}
