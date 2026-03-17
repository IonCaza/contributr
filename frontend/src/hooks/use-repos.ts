import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useProjectRepos(projectId: string) {
  return useQuery({
    queryKey: queryKeys.repos.list(projectId),
    queryFn: () => api.listRepos(projectId),
    enabled: !!projectId,
  });
}

export function useRepo(id: string) {
  return useQuery({
    queryKey: queryKeys.repos.detail(id),
    queryFn: () => api.getRepo(id),
    enabled: !!id,
  });
}

export function useRepoStats(id: string, filters?: { branches?: string[]; from?: string; to?: string }) {
  return useQuery({
    queryKey: queryKeys.repos.stats(id, filters),
    queryFn: () => api.getRepoStats(id, { branches: filters?.branches, from_date: filters?.from, to_date: filters?.to }),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useSyncJobs(repoId: string) {
  return useQuery({
    queryKey: queryKeys.repos.syncJobs(repoId),
    queryFn: () => api.listSyncJobs(repoId),
    enabled: !!repoId,
    refetchInterval: (query) => {
      const jobs = query.state.data;
      return jobs?.some((j: { status: string }) => j.status === "queued" || j.status === "running")
        ? 3000
        : false;
    },
  });
}

export function useRepoBranches(repoId: string, contributorId?: string) {
  return useQuery({
    queryKey: queryKeys.repos.branches(repoId, contributorId),
    queryFn: () => api.listBranches(repoId, contributorId),
    enabled: !!repoId,
  });
}

export function useRepoContributors(repoId: string, branches?: string[]) {
  return useQuery({
    queryKey: queryKeys.repos.contributors(repoId, branches),
    queryFn: () => api.listRepoContributors(repoId, branches),
    enabled: !!repoId,
  });
}

export function useFileTree(repoId: string, branch?: string) {
  return useQuery({
    queryKey: queryKeys.repos.fileTree(repoId, branch),
    queryFn: () => api.getFileTree(repoId, branch),
    enabled: !!repoId,
  });
}

export function useRepoCommits(
  repoId: string,
  filters?: { branch?: string[]; search?: string; page?: number; per_page?: number },
) {
  return useQuery({
    queryKey: queryKeys.repos.commits(repoId, filters),
    queryFn: () => api.listRepoCommits(repoId, filters),
    enabled: !!repoId,
    placeholderData: keepPreviousData,
  });
}

export function useCreateRepo(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createRepo(projectId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) }); },
  });
}

export function useUpdateRepo(repoId: string, projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => api.updateRepo(repoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.repos.detail(repoId) });
      qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    },
  });
}

export function useDeleteRepo(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (repoId: string) => api.deleteRepo(repoId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) }); },
  });
}

export function useSyncRepo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (repoId: string) => api.syncRepo(repoId),
    onSuccess: (_data, repoId) => { qc.invalidateQueries({ queryKey: queryKeys.repos.syncJobs(repoId) }); },
  });
}

export function useCancelSync(repoId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.cancelSyncJob(repoId, jobId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.repos.syncJobs(repoId) }); },
  });
}

export function usePurgeRepo(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (repoId: string) => api.purgeRepoData(repoId),
    onSuccess: (_data, repoId) => {
      qc.invalidateQueries({ queryKey: ["repos", repoId] });
      qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.projects.stats(projectId) });
    },
  });
}
