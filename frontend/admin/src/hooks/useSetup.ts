import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { SetupPayload, SetupStatus, Squad } from "@/types/api";

export function useSetupStatus() {
  return useQuery({
    queryKey: ["setup-status"],
    queryFn: async () => (await api.get<SetupStatus>("/admin/setup/status")).data,
  });
}

export function useSquads(enabled = true) {
  return useQuery({
    queryKey: ["squads"],
    queryFn: async () => (await api.get<Squad[]>("/admin/setup/squads")).data,
    enabled,
  });
}

export function useCompleteSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SetupPayload) =>
      (await api.post<SetupStatus>("/admin/setup/", payload)).data,
    // The answer IS the new setup status, so it goes straight into the cache: invalidated and not
    // awaited, the gate the caller navigates through still read the cached `completed: false` and
    // put the wizard back up — with its default values — until the refetch landed.
    onSuccess: (status) => {
      qc.setQueryData(["setup-status"], status);
      return qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}
