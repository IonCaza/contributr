import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useTeams(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.teams.all(projectId),
    queryFn: () => api.listTeams(projectId),
  });
}

export function useTeam(id: string) {
  return useQuery({
    queryKey: queryKeys.teams.detail(id),
    queryFn: () => api.getTeam(id),
    enabled: !!id,
  });
}

export function useTeamMembers(teamId: string) {
  return useQuery({
    queryKey: queryKeys.teams.members(teamId),
    queryFn: () => api.listTeamMembers(teamId),
    enabled: !!teamId,
  });
}

export function useCreateTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { project_id: string; name: string; description?: string }) =>
      api.createTeam(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useUpdateTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string } }) =>
      api.updateTeam(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useDeleteTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTeam(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useAddTeamMember(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { contributor_id: string; role?: string }) =>
      api.addTeamMember(teamId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.teams.members(teamId) });
      qc.invalidateQueries({ queryKey: queryKeys.teams.detail(teamId) });
    },
  });
}

export function useRemoveTeamMember(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contributorId: string) => api.removeTeamMember(teamId, contributorId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.teams.members(teamId) });
      qc.invalidateQueries({ queryKey: queryKeys.teams.detail(teamId) });
    },
  });
}
