import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { BotUser, UserAction, UserListParams, UserPage } from "@/types/api";

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
    queryFn: async () => (await api.get<BotUser>(`/admin/users/${id}`)).data,
    enabled: id != null,
  });
}

export function useUserAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: number; action: UserAction }) =>
      (await api.post<BotUser>(`/admin/users/${id}/${action}`)).data,
    onSuccess: (updated) => {
      qc.setQueryData(["user", updated.telegram_id], updated);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
