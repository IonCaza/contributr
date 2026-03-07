"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface TeamInsightFilters {
  category?: string;
  severity?: string;
  status?: string;
}

export function useTeamInsightFindings(projectId: string, teamId: string, filters?: TeamInsightFilters) {
  return useQuery({
    queryKey: queryKeys.teamInsights.findings(projectId, teamId, filters as Record<string, unknown>),
    queryFn: () => api.listTeamInsightFindings(projectId, teamId, filters),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamInsightsSummary(projectId: string, teamId: string) {
  return useQuery({
    queryKey: queryKeys.teamInsights.summary(projectId, teamId),
    queryFn: () => api.getTeamInsightsSummary(projectId, teamId),
    enabled: !!projectId && !!teamId,
  });
}

export function useTeamInsightRuns(projectId: string, teamId: string) {
  return useQuery({
    queryKey: queryKeys.teamInsights.runs(projectId, teamId),
    queryFn: () => api.listTeamInsightRuns(projectId, teamId),
    enabled: !!projectId && !!teamId,
  });
}

export function useTriggerTeamInsightRun(projectId: string, teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerTeamInsightRun(projectId, teamId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.teamInsights.runs(projectId, teamId) });
      qc.invalidateQueries({ queryKey: queryKeys.teamInsights.summary(projectId, teamId) });
      qc.invalidateQueries({ queryKey: queryKeys.teamInsights.findings(projectId, teamId) });
    },
  });
}

export function useDismissTeamInsightFinding(projectId: string, teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.dismissTeamInsightFinding(projectId, teamId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.teamInsights.findings(projectId, teamId) });
      qc.invalidateQueries({ queryKey: queryKeys.teamInsights.summary(projectId, teamId) });
    },
  });
}
