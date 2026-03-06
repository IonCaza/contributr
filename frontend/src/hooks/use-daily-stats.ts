import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useDailyStats(params: Record<string, string | string[] | undefined>) {
  return useQuery({
    queryKey: queryKeys.daily(params),
    queryFn: () => api.dailyStats(params),
    placeholderData: keepPreviousData,
  });
}

export function useTrends(params: Record<string, string | string[] | undefined>) {
  return useQuery({
    queryKey: queryKeys.trends(params),
    queryFn: () => api.trends(params),
    placeholderData: keepPreviousData,
  });
}
