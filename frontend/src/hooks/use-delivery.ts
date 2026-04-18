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

export function useDeliverySyncJobs(projectId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.syncJobs(projectId),
    queryFn: () => api.listDeliverySyncJobs(projectId),
    enabled: !!projectId,
    refetchInterval: (query) => {
      const jobs = query.state.data;
      return jobs?.some((j: { status: string }) => j.status === "queued" || j.status === "running")
        ? 3000
        : false;
    },
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

export function useWorkItemDetail(projectId: string, workItemId: string, opts?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemDetail(projectId, workItemId),
    queryFn: () => api.getWorkItemDetail(projectId, workItemId),
    enabled: !!projectId && !!workItemId,
    refetchInterval: opts?.refetchInterval,
  });
}

export function useUpdateWorkItem(projectId: string, workItemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { description?: string; title?: string }) =>
      api.updateWorkItem(projectId, workItemId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.delivery.workItemDetail(projectId, workItemId) });
    },
  });
}

export function usePullWorkItem(projectId: string, workItemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.pullWorkItem(projectId, workItemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.delivery.workItemDetail(projectId, workItemId) });
    },
  });
}

export function useAcceptDraft(projectId: string, workItemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.acceptWorkItemDraft(projectId, workItemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.delivery.workItemDetail(projectId, workItemId) });
    },
  });
}

export function useDiscardDraft(projectId: string, workItemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.discardWorkItemDraft(projectId, workItemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.delivery.workItemDetail(projectId, workItemId) });
    },
  });
}

export function useWorkItemCommits(projectId: string, workItemId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemCommits(projectId, workItemId),
    queryFn: () => api.getWorkItemCommits(projectId, workItemId),
    enabled: !!projectId && !!workItemId,
  });
}

export function useWorkItemActivities(projectId: string, workItemId: string, params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemActivities(projectId, workItemId, params),
    queryFn: () => api.getWorkItemActivities(projectId, workItemId, params),
    enabled: !!projectId && !!workItemId,
  });
}

export function useContributorActivities(projectId: string, contributorId: string, params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: queryKeys.delivery.contributorActivities(projectId, contributorId, params),
    queryFn: () => api.getContributorActivities(projectId, contributorId, params),
    enabled: !!projectId && !!contributorId,
  });
}

export function useContributorActivityMetrics(projectId: string, contributorId: string, params?: { from_date?: string; to_date?: string }) {
  return useQuery({
    queryKey: queryKeys.delivery.contributorActivityMetrics(projectId, contributorId, params),
    queryFn: () => api.getContributorActivityMetrics(projectId, contributorId, params),
    enabled: !!projectId && !!contributorId,
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

export function useCarryoverSummary(projectId: string, params?: { team_id?: string; from_date?: string; to_date?: string }) {
  return useQuery({
    queryKey: queryKeys.delivery.carryoverSummary(projectId, params),
    queryFn: () => api.getCarryoverSummary(projectId, params),
    enabled: !!projectId,
  });
}

export function useCarryoverBySprint(projectId: string, params?: { team_id?: string; limit?: number }) {
  return useQuery({
    queryKey: queryKeys.delivery.carryoverBySprint(projectId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getCarryoverBySprint(projectId, params),
    enabled: !!projectId,
  });
}

export function useCarryoverItems(projectId: string, params?: { team_id?: string; min_moves?: number; from_date?: string; to_date?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: queryKeys.delivery.carryoverItems(projectId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getCarryoverItems(projectId, params),
    enabled: !!projectId,
  });
}

export function useWorkItemIterationHistory(projectId: string, workItemId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.delivery.workItemIterationHistory(projectId, workItemId),
    queryFn: () => api.getWorkItemIterationHistory(projectId, workItemId),
    enabled: !!projectId && !!workItemId && enabled,
  });
}

export function useTeamCapacityVsLoad(projectId: string, teamId: string, params?: { iteration_id?: string }) {
  return useQuery({
    queryKey: queryKeys.delivery.teamCapacity(projectId, teamId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getTeamCapacityVsLoad(projectId, teamId, params),
    enabled: !!projectId && !!teamId,
  });
}

export function useBacklogFeatureRollup(projectId: string, params?: { team_id?: string; include_completed_features?: boolean; limit?: number }) {
  return useQuery({
    queryKey: queryKeys.delivery.featureRollup(projectId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getBacklogFeatureRollup(projectId, params),
    enabled: !!projectId,
  });
}

export function useBacklogSizingTrend(projectId: string, params?: { team_id?: string; weeks?: number; include_unsized?: boolean; story_only?: boolean; basis?: "created_at" | "activated_at" }) {
  return useQuery({
    queryKey: queryKeys.delivery.sizingTrend(projectId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getBacklogSizingTrend(projectId, params),
    enabled: !!projectId,
  });
}

export function useBacklogTrustedScorecard(projectId: string, params?: { team_id?: string }) {
  return useQuery({
    queryKey: queryKeys.delivery.trustedScorecard(projectId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getBacklogTrustedScorecard(projectId, params),
    enabled: !!projectId,
  });
}

export function useLongRunningStories(projectId: string, params?: { team_id?: string; min_days_active?: number; include_bugs?: boolean; limit?: number }) {
  return useQuery({
    queryKey: queryKeys.delivery.longRunning(projectId, params as Record<string, unknown> | undefined),
    queryFn: () => api.getLongRunningStories(projectId, params),
    enabled: !!projectId,
  });
}

export function useDeliverySettings(projectId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.delivery.settings(projectId),
    queryFn: () => api.getDeliverySettings(projectId),
    enabled: !!projectId && enabled,
  });
}

export function useUpdateDeliverySettings(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof api.updateDeliverySettings>[1]) => api.updateDeliverySettings(projectId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.delivery.settings(projectId) });
    },
  });
}

export function useDeliverySettingsAvailableStates(projectId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.delivery.settingsStates(projectId),
    queryFn: () => api.getDeliverySettingsAvailableStates(projectId),
    enabled: !!projectId && enabled,
  });
}

export function useDeliverySettingsAvailableCustomFields(projectId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.delivery.settingsCustomFields(projectId),
    queryFn: () => api.getDeliverySettingsAvailableCustomFields(projectId),
    enabled: !!projectId && enabled,
  });
}
