"use client";

import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface DepFilters {
  severity?: string;
  ecosystem?: string;
  outdated?: boolean;
  vulnerable?: boolean;
  status?: string;
  file_path?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

// ── Repository-scoped ───────────────────────────────────────────────

export function useDepFindings(repoId: string, filters?: DepFilters) {
  return useQuery({
    queryKey: queryKeys.dependencies.findings(repoId, "repo", filters ? { ...filters } : undefined),
    queryFn: () => api.listDepFindings(repoId, filters),
    enabled: !!repoId,
  });
}

export function useDepSummary(repoId: string) {
  return useQuery({
    queryKey: queryKeys.dependencies.summary(repoId, "repo"),
    queryFn: () => api.getDepSummary(repoId),
    enabled: !!repoId,
  });
}

export function useDepRuns(repoId: string) {
  return useQuery({
    queryKey: queryKeys.dependencies.runs(repoId, "repo"),
    queryFn: () => api.listDepRuns(repoId),
    enabled: !!repoId,
  });
}

export function useTriggerDepScan(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerDepScan(repoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.runs(repoId, "repo") });
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.summary(repoId, "repo") });
    },
  });
}

export function useDismissDepFinding(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.dismissDepFinding(repoId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.findings(repoId, "repo") });
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.summary(repoId, "repo") });
    },
  });
}

// ── Project-scoped ──────────────────────────────────────────────────

export function useProjectDepFindings(projectId: string, filters?: DepFilters) {
  return useQuery({
    queryKey: queryKeys.dependencies.findings(projectId, "project", filters ? { ...filters } : undefined),
    queryFn: () => api.listProjectDepFindings(projectId, filters),
    enabled: !!projectId,
    placeholderData: keepPreviousData,
  });
}

export function useProjectDepSummary(projectId: string) {
  return useQuery({
    queryKey: queryKeys.dependencies.summary(projectId, "project"),
    queryFn: () => api.getProjectDepSummary(projectId),
    enabled: !!projectId,
  });
}

export function useProjectDepRuns(projectId: string) {
  return useQuery({
    queryKey: queryKeys.dependencies.runs(projectId, "project"),
    queryFn: () => api.listProjectDepRuns(projectId),
    enabled: !!projectId,
  });
}

export function useTriggerProjectDepScan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (repoId: string) => api.triggerDepScan(repoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.runs(projectId, "project") });
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.summary(projectId, "project") });
    },
  });
}

export function useDismissProjectDepFinding(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ repoId, findingId }: { repoId: string; findingId: string }) =>
      api.dismissDepFinding(repoId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.findings(projectId, "project") });
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.summary(projectId, "project") });
    },
  });
}

// ── Settings ────────────────────────────────────────────────────────

export function useDepSettings() {
  return useQuery({
    queryKey: queryKeys.dependencies.settings,
    queryFn: () => api.getDepSettings(),
  });
}

export function useUpdateDepSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { auto_dep_scan_on_sync: boolean }) => api.updateDepSettings(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.dependencies.settings });
    },
  });
}
