"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface SastFilters {
  severity?: string;
  status?: string;
  file_path?: string;
  rule_id?: string;
}

// ── Repository-scoped ───────────────────────────────────────────────

export function useSastFindings(repoId: string, filters?: SastFilters) {
  return useQuery({
    queryKey: queryKeys.sast.findings(repoId, "repo", filters ? { ...filters } : undefined),
    queryFn: () => api.listSastFindings(repoId, filters),
  });
}

export function useSastSummary(repoId: string) {
  return useQuery({
    queryKey: queryKeys.sast.summary(repoId, "repo"),
    queryFn: () => api.getSastSummary(repoId),
  });
}

export function useSastRuns(repoId: string) {
  return useQuery({
    queryKey: queryKeys.sast.runs(repoId, "repo"),
    queryFn: () => api.listSastRuns(repoId),
  });
}

export function useTriggerSastScan(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data?: { branch?: string; profile_id?: string }) =>
      api.triggerSastScan(repoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.runs(repoId, "repo") });
      qc.invalidateQueries({ queryKey: queryKeys.sast.summary(repoId, "repo") });
    },
  });
}

export function useDismissSastFinding(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.dismissSastFinding(repoId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.findings(repoId, "repo") });
      qc.invalidateQueries({ queryKey: queryKeys.sast.summary(repoId, "repo") });
    },
  });
}

export function useMarkSastFalsePositive(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.markSastFalsePositive(repoId, findingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.findings(repoId, "repo") });
      qc.invalidateQueries({ queryKey: queryKeys.sast.summary(repoId, "repo") });
    },
  });
}

// ── Project-scoped ──────────────────────────────────────────────────

export function useProjectSastFindings(projectId: string, filters?: SastFilters) {
  return useQuery({
    queryKey: queryKeys.sast.findings(projectId, "project", filters ? { ...filters } : undefined),
    queryFn: () => api.listProjectSastFindings(projectId, filters),
  });
}

export function useProjectSastSummary(projectId: string) {
  return useQuery({
    queryKey: queryKeys.sast.summary(projectId, "project"),
    queryFn: () => api.getProjectSastSummary(projectId),
  });
}

export function useProjectSastRuns(projectId: string) {
  return useQuery({
    queryKey: queryKeys.sast.runs(projectId, "project"),
    queryFn: () => api.listProjectSastRuns(projectId),
  });
}

// ── Rule Profiles ───────────────────────────────────────────────────

export function useSastProfiles() {
  return useQuery({
    queryKey: queryKeys.sast.profiles,
    queryFn: () => api.listSastProfiles(),
  });
}

export function useCreateSastProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; rulesets?: string[]; custom_rules_yaml?: string; is_default?: boolean }) =>
      api.createSastProfile(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.profiles });
    },
  });
}

export function useUpdateSastProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; description?: string; rulesets?: string[]; custom_rules_yaml?: string; is_default?: boolean }) =>
      api.updateSastProfile(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.profiles });
    },
  });
}

export function useDeleteSastProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteSastProfile(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.profiles });
    },
  });
}

// ── Settings ────────────────────────────────────────────────────────

export function useSastSettings() {
  return useQuery({
    queryKey: queryKeys.sast.settings,
    queryFn: () => api.getSastSettings(),
  });
}

export function useUpdateSastSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { auto_sast_on_sync: boolean }) => api.updateSastSettings(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.settings });
    },
  });
}

// ── Ignored Rules ───────────────────────────────────────────────────

export function useGlobalIgnoredRules() {
  return useQuery({
    queryKey: queryKeys.sast.ignoredRules("global"),
    queryFn: () => api.listGlobalIgnoredRules(),
  });
}

export function useAddGlobalIgnoredRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { rule_id: string; reason?: string }) => api.addGlobalIgnoredRule(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.ignoredRules("global") });
    },
  });
}

export function useRemoveGlobalIgnoredRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.removeGlobalIgnoredRule(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.ignoredRules("global") });
    },
  });
}

export function useRepoIgnoredRules(repoId: string) {
  return useQuery({
    queryKey: queryKeys.sast.ignoredRules(repoId),
    queryFn: () => api.listRepoIgnoredRules(repoId),
    enabled: !!repoId,
  });
}

export function useAddRepoIgnoredRule(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { rule_id: string; reason?: string }) => api.addRepoIgnoredRule(repoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sast.ignoredRules(repoId) });
    },
  });
}
