import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { DateRange } from "@/components/date-range-filter";

function rangeParams(range?: DateRange) {
  if (!range) return undefined;
  return { from_date: range.from, to_date: range.to };
}

export function useTeamCodeStats(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.codeStats(projectId, teamId, range),
    queryFn: () => api.getTeamCodeStats(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamCodeActivity(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.codeActivity(projectId, teamId, range),
    queryFn: () => api.getTeamCodeActivity(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamMemberStats(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.memberStats(projectId, teamId, range),
    queryFn: () => api.getTeamMemberStats(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamDeliveryStats(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.deliveryStats(projectId, teamId, range),
    queryFn: () => api.getTeamDeliveryStats(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamDeliveryVelocity(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.deliveryVelocity(projectId, teamId, range),
    queryFn: () => api.getTeamDeliveryVelocity(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamDeliveryFlow(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.deliveryFlow(projectId, teamId, range),
    queryFn: () => api.getTeamDeliveryFlow(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamDeliveryBacklog(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.deliveryBacklog(projectId, teamId, range),
    queryFn: () => api.getTeamDeliveryBacklog(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamDeliveryQuality(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.deliveryQuality(projectId, teamId, range),
    queryFn: () => api.getTeamDeliveryQuality(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamDeliveryIntersection(projectId: string, teamId: string, range?: DateRange) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.deliveryIntersection(projectId, teamId, range),
    queryFn: () => api.getTeamDeliveryIntersection(projectId, teamId, rangeParams(range)),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamWorkItems(
  projectId: string,
  teamId: string,
  filters?: { state?: string; search?: string; page?: number; page_size?: number },
) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.workItems(projectId, teamId, filters),
    queryFn: () => api.getTeamWorkItems(projectId, teamId, filters),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamInsights(projectId: string, teamId: string) {
  return useQuery({
    queryKey: queryKeys.teamAnalytics.insights(projectId, teamId),
    queryFn: () => api.getTeamInsights(projectId, teamId),
    enabled: !!projectId && !!teamId,
  });
}
