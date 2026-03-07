import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { DeliveryFilters } from "@/lib/types";

export function useDeliveryStats(projectId: string, filters?: DeliveryFilters) {
  return useQuery({
    queryKey: queryKeys.delivery.stats(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getDeliveryStats(projectId, filters),
    enabled: !!projectId,
  });
}

export function useWorkItems(
  projectId: string,
  filters?: {
    work_item_type?: string;
    state?: string;
    assignee_id?: string;
    iteration_ids?: string[];
    parent_id?: string;
    search?: string;
    from_date?: string;
    to_date?: string;
    resolved_from?: string;
    resolved_to?: string;
    closed_from?: string;
    closed_to?: string;
    priority?: number;
    story_points_min?: number;
    story_points_max?: number;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  },
) {
  return useQuery({
    queryKey: queryKeys.delivery.workItems(projectId, filters),
    queryFn: () => api.listWorkItems(projectId, filters),
    enabled: !!projectId,
  });
}

export function useWorkItemsTree(
  projectId: string,
  filters?: {
    work_item_type?: string;
    state?: string;
    assignee_id?: string;
    iteration_ids?: string[];
    search?: string;
    from_date?: string;
    to_date?: string;
    resolved_from?: string;
    resolved_to?: string;
    closed_from?: string;
    closed_to?: string;
    priority?: number;
    story_points_min?: number;
    story_points_max?: number;
    sort_by?: string;
    sort_order?: string;
    max_items?: number;
  },
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemsTree(projectId, filters),
    queryFn: () => api.getWorkItemsTree(projectId, filters),
    enabled: !!projectId && (options?.enabled !== false),
  });
}

export function useIterations(projectId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.iterations(projectId),
    queryFn: () => api.listIterations(projectId),
    enabled: !!projectId,
  });
}

export function useVelocity(projectId: string, filters?: { limit?: number; iteration_ids?: string[] }) {
  return useQuery({
    queryKey: queryKeys.delivery.velocity(projectId, filters),
    queryFn: () => api.getVelocity(projectId, filters),
    enabled: !!projectId,
  });
}

export function useDeliveryTrends(projectId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.trends(projectId),
    queryFn: () => api.getDeliveryTrends(projectId),
    enabled: !!projectId,
  });
}

export function useDeliverySyncJobs(projectId: string, polling = false) {
  return useQuery({
    queryKey: queryKeys.delivery.syncJobs(projectId),
    queryFn: () => api.listDeliverySyncJobs(projectId),
    enabled: !!projectId,
    refetchInterval: polling ? 3000 : false,
  });
}

export function useTriggerDeliverySync(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerDeliverySync(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.delivery.syncJobs(projectId) });
    },
  });
}

export function usePurgeDelivery(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.purgeDelivery(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["delivery", projectId] });
    },
  });
}

export function useFlowMetrics(projectId: string, filters?: DeliveryFilters) {
  return useQuery({
    queryKey: queryKeys.delivery.flow(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getFlowMetrics(projectId, filters),
    enabled: !!projectId,
  });
}

export function useBacklogHealth(projectId: string, filters?: DeliveryFilters) {
  return useQuery({
    queryKey: queryKeys.delivery.backlogHealth(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getBacklogHealth(projectId, filters),
    enabled: !!projectId,
  });
}

export function useQualityMetrics(projectId: string, filters?: DeliveryFilters) {
  return useQuery({
    queryKey: queryKeys.delivery.quality(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getQualityMetrics(projectId, filters),
    enabled: !!projectId,
  });
}

export function useIntersectionMetrics(projectId: string, filters?: DeliveryFilters) {
  return useQuery({
    queryKey: queryKeys.delivery.intersection(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getIntersectionMetrics(projectId, filters),
    enabled: !!projectId,
  });
}

export function useWorkItemDetail(projectId: string, workItemId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemDetail(projectId, workItemId),
    queryFn: () => api.getWorkItemDetail(projectId, workItemId),
    enabled: !!projectId && !!workItemId,
  });
}

export function useWorkItemCommits(projectId: string, workItemId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemCommits(projectId, workItemId),
    queryFn: () => api.getWorkItemCommits(projectId, workItemId),
    enabled: !!projectId && !!workItemId,
  });
}

export function useSprintDetail(projectId: string, iterationId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.sprintDetail(projectId, iterationId),
    queryFn: () => api.getSprintDetail(projectId, iterationId),
    enabled: !!projectId && !!iterationId,
  });
}

export function useSprintBurndown(projectId: string, iterationId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.sprintBurndown(projectId, iterationId),
    queryFn: () => api.getSprintBurndown(projectId, iterationId),
    enabled: !!projectId && !!iterationId,
  });
}

export function useTeamDetail(projectId: string, teamId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.teamDetail(projectId, teamId),
    queryFn: () => api.getTeamDetail(projectId, teamId),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeams(projectId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.teams(projectId),
    queryFn: () => api.listDeliveryTeams(projectId),
    enabled: !!projectId,
  });
}

export function useItemDetails(projectId: string, filters?: DeliveryFilters, enabled = true) {
  return useQuery({
    queryKey: queryKeys.delivery.itemDetails(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getItemDetails(projectId, filters),
    enabled: !!projectId && enabled,
  });
}

export function useContributorDeliverySummary(projectId: string, filters?: DeliveryFilters, enabled = true) {
  return useQuery({
    queryKey: queryKeys.delivery.contributorSummary(projectId, filters as Record<string, unknown> | undefined),
    queryFn: () => api.getContributorSummary(projectId, filters),
    enabled: !!projectId && enabled,
  });
}
