import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useContributors(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.contributors.all(projectId),
    queryFn: () => api.listContributors(projectId),
  });
}

export function useDuplicateContributors() {
  return useQuery({
    queryKey: queryKeys.contributors.duplicates,
    queryFn: () => api.getDuplicateContributors(),
  });
}

export function useContributor(id: string) {
  return useQuery({
    queryKey: queryKeys.contributors.detail(id),
    queryFn: () => api.getContributor(id),
    enabled: !!id,
  });
}

export function useContributorStats(
  id: string,
  filters?: { from_date?: string; to_date?: string; repository_id?: string; branch?: string[] },
) {
  return useQuery({
    queryKey: queryKeys.contributors.stats(id, filters),
    queryFn: () => api.getContributorStats(id, filters),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useContributorRepos(id: string) {
  return useQuery({
    queryKey: queryKeys.contributors.repos(id),
    queryFn: () => api.getContributorRepos(id),
    enabled: !!id,
  });
}

export function useContributorCommits(
  id: string,
  filters?: { repository_id?: string; branch?: string[]; from_date?: string; to_date?: string; search?: string; page?: number; per_page?: number },
) {
  return useQuery({
    queryKey: queryKeys.contributors.commits(id, filters),
    queryFn: () => api.listContributorCommits(id, filters),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useMergeContributors() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      api.mergeContributors(sourceId, targetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contributors"] });
      qc.invalidateQueries({ queryKey: queryKeys.contributors.duplicates });
    },
  });
}
