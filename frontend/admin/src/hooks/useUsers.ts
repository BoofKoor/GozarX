import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { BotUser, BotUserDetail, UserAction, UserListParams, UserPage } from "@/types/api";

export function useUsers(params: UserListParams) {
  return useQuery({
    queryKey: ["users", params],
    queryFn: async () => (await api.get<UserPage>("/admin/users/", { params })).data,
    placeholderData: keepPreviousData, // keep the current page visible while the next loads
  });
}

export function useUser(id: number | null) {
  return useQuery({
    queryKey: ["user", id],
    queryFn: async () => (await api.get<BotUserDetail>(`/admin/users/${id}/detail`)).data,
    enabled: id != null,
  });
}

/** Locations the list can be filtered by — the ones a config was actually claimed from. */
export function useClaimedLocations() {
  return useQuery({
    queryKey: ["users", "locations"],
    queryFn: async () => (await api.get<string[]>("/admin/users/locations")).data,
    staleTime: 5 * 60_000, // the set changes when the squad does, not between page views
  });
}

/** Download the CURRENT filter as CSV. Authenticated, so a plain <a href> would 401. */
export async function downloadUsersCsv(params: UserListParams): Promise<void> {
  const res = await api.get("/admin/users/export.csv", {
    params: { status: params.status, search: params.search, location: params.location },
    responseType: "blob",
  });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "gozar-users.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function useUserAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: number; action: UserAction }) =>
      (await api.post<BotUser>(`/admin/users/${id}/${action}`)).data,
    onSuccess: (updated) => {
      qc.setQueryData(["user", updated.telegram_id], updated);
      qc.invalidateQueries({ queryKey: ["users"] });
      // A ban/unban/reclaim shifts the status counts the dashboard shows, so refresh it too.
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
