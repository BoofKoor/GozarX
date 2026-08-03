import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { DashboardAnalytics, DashboardStats, Retention } from "@/types/api";

/** The windows the backend accepts. Anything else is clamped server-side to 14. */
export const RANGES = [7, 14, 30, 90] as const;
export type Range = (typeof RANGES)[number];

/** Dashboard stats for a chart window. keepPreviousData holds the current view while a range switch
 * refetches (no skeleton flash). */
export function useDashboard(days: number) {
  return useQuery({
    queryKey: ["dashboard", days],
    queryFn: async () =>
      (await api.get<DashboardStats>("/admin/dashboard/stats", { params: { days } })).data,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
  });
}

/** Deeper analytics (DAU/WAU/MAU, funnel, heatmaps, new-vs-returning, …) — a separate,
 * less-frequent query so the cheap headline stats stay snappy. */
export function useDashboardAnalytics(days: number) {
  return useQuery({
    queryKey: ["dashboard-analytics", days],
    queryFn: async () =>
      (await api.get<DashboardAnalytics>("/admin/dashboard/analytics", { params: { days } })).data,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

/** Weekly signup cohorts and how much of each came back. Not windowed by the page range — cohorts
 * are inherently weekly, so this has its own `weeks` axis. */
export function useRetention(weeks = 8) {
  return useQuery({
    queryKey: ["dashboard-retention", weeks],
    queryFn: async () =>
      (await api.get<Retention>("/admin/dashboard/retention", { params: { weeks } })).data,
    placeholderData: keepPreviousData,
  });
}

/** Download the window's daily series as CSV. Uses the authenticated axios client (the export is
 * JWT-gated, so a plain <a href> would 401) and hands the blob to a temporary link. */
export async function downloadDashboardCsv(days: number): Promise<void> {
  const res = await api.get("/admin/dashboard/export.csv", {
    params: { days },
    responseType: "blob",
  });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `gozar-dashboard-${days}d.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
