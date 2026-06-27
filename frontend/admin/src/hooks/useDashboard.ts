import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { DashboardStats } from "@/types/api";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardStats>("/admin/dashboard/stats")).data,
    refetchInterval: 30_000,
  });
}
