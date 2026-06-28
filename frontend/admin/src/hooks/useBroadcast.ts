import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { BroadcastAudience, BroadcastResult, BroadcastSend, Lang } from "@/types/api";

/** Live recipient count for the chosen language groups. ``languages`` is sent as a comma-separated
 *  query param (empty ⇒ everyone); the query key includes it so the count refetches on each change. */
export function useAudience(languages: Lang[]) {
  const param = languages.join(",");
  return useQuery({
    queryKey: ["broadcast-audience", param],
    queryFn: async () =>
      (await api.get<BroadcastAudience>("/admin/broadcast/", { params: { languages: param } }))
        .data,
  });
}

export function useSendBroadcast() {
  return useMutation({
    mutationFn: async (body: BroadcastSend) =>
      (await api.post<BroadcastResult>("/admin/broadcast/", body)).data,
  });
}
