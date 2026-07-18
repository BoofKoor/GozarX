import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { DashboardAnalytics, DashboardStats } from "@/types/api";

/** Dashboard stats for a chart window (7/14/30 days). The backend clamps unsupported values.
 * keepPreviousData holds the current view while a range switch refetches (no skeleton flash). */
export function useDashboard(days: number) {
  return useQuery({
    queryKey: ["dashboard", days],
    queryFn: async () =>
      (await api.get<DashboardStats>("/admin/dashboard/stats", { params: { days } })).data,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
  });
}

/** Deeper analytics (DAU/WAU/MAU, funnel, heatmap, …) — a separate, less-frequent query so the
 * cheap headline stats stay snappy. */
export function useDashboardAnalytics(days: number) {
  return useQuery({
    queryKey: ["dashboard-analytics", days],
    queryFn: async () =>
      (await api.get<DashboardAnalytics>("/admin/dashboard/analytics", { params: { days } })).data,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}
