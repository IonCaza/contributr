import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useDeliveryStats(projectId: string, filters?: { team_id?: string; contributor_id?: string }) {
  return useQuery({
    queryKey: queryKeys.delivery.stats(projectId, filters),
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
    iteration_id?: string;
    parent_id?: string;
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

export function useIterations(projectId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.iterations(projectId),
    queryFn: () => api.listIterations(projectId),
    enabled: !!projectId,
  });
}

export function useVelocity(projectId: string) {
  return useQuery({
    queryKey: queryKeys.delivery.velocity(projectId),
    queryFn: () => api.getVelocity(projectId),
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
