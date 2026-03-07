import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function useCustomFields(projectId: string | undefined) {
  return useQuery({
    queryKey: ["custom-fields", projectId],
    queryFn: () => api.listCustomFields(projectId!),
    enabled: !!projectId,
  });
}

export function useDiscoverCustomFields(projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.discoverCustomFields(projectId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-fields", projectId] });
    },
  });
}

export function useBulkUpsertCustomFields(projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fields: { field_reference_name: string; display_name: string; field_type: string; enabled: boolean }[]) =>
      api.bulkUpsertCustomFields(projectId!, fields),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-fields", projectId] });
    },
  });
}

export function useDeleteCustomField(projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (configId: string) => api.deleteCustomField(projectId!, configId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-fields", projectId] });
    },
  });
}
