"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface ContributorInsightFilters {
  category?: string;
  severity?: string;
  status?: string;
}

export function useContributorInsightFindings(contributorId: string, filters?: ContributorInsightFilters) {
  return useQuery({
    queryKey: queryKeys.contributorInsights.findings(contributorId, filters ? { ...filters } : undefined),
    queryFn: () => api.listContributorInsightFindings(contributorId, filters),
  });
}

export function useContributorInsightsSummary(contributorId: string) {
  return useQuery({
    queryKey: queryKeys.contributorInsights.summary(contributorId),
    queryFn: () => api.getContributorInsightsSummary(contributorId),
  });
}

export function useContributorInsightRuns(contributorId: string) {
  return useQuery({
    queryKey: queryKeys.contributorInsights.runs(contributorId),
    queryFn: () => api.listContributorInsightRuns(contributorId),
  });
}

export function useTriggerContributorInsightRun(contributorId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerContributorInsightRun(contributorId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.contributorInsights.runs(contributorId) });
      qc.invalidateQueries({ queryKey: queryKeys.contributorInsights.summary(contributorId) });
      qc.invalidateQueries({ queryKey: queryKeys.contributorInsights.findings(contributorId) });
    },
  });
}

export function useDismissContributorInsightFinding(contributorId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.dismissContributorInsightFinding(contributorId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.contributorInsights.findings(contributorId) });
      qc.invalidateQueries({ queryKey: queryKeys.contributorInsights.summary(contributorId) });
    },
  });
}
