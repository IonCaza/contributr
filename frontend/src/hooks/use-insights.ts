"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface InsightFilters {
  category?: string;
  severity?: string;
  status?: string;
}

export function useInsightFindings(projectId: string, filters?: InsightFilters) {
  return useQuery({
    queryKey: queryKeys.insights.findings(projectId, filters ? { ...filters } : undefined),
    queryFn: () => api.listInsightFindings(projectId, filters),
  });
}

export function useInsightsSummary(projectId: string) {
  return useQuery({
    queryKey: queryKeys.insights.summary(projectId),
    queryFn: () => api.getInsightsSummary(projectId),
  });
}

export function useInsightRuns(projectId: string) {
  return useQuery({
    queryKey: queryKeys.insights.runs(projectId),
    queryFn: () => api.listInsightRuns(projectId),
  });
}

export function useTriggerInsightRun(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerInsightRun(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.insights.runs(projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.insights.summary(projectId) });
    },
  });
}

export function useDismissInsightFinding(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.dismissInsightFinding(projectId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.insights.findings(projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.insights.summary(projectId) });
    },
  });
}
