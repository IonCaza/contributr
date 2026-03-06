import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.all,
    queryFn: () => api.listProjects(),
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: queryKeys.projects.detail(id),
    queryFn: () => api.getProject(id),
    enabled: !!id,
  });
}

export function useProjectStats(id: string, range?: { from?: string; to?: string }) {
  return useQuery({
    queryKey: queryKeys.projects.stats(id, range),
    queryFn: () => api.getProjectStats(id, { from_date: range?.from, to_date: range?.to }),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useProjectPRStats(id: string) {
  return useQuery({
    queryKey: queryKeys.projects.prStats(id),
    queryFn: () => api.getProjectPRStats(id),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) => api.createProject(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.projects.all }); },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.projects.all }); },
  });
}

export function useUpdateProject(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name?: string; description?: string; platform_credential_id?: string | null }) =>
      api.updateProject(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.projects.all });
    },
  });
}
