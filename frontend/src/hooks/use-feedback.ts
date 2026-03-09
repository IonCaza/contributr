import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface FeedbackFilters {
  source?: string;
  status?: string;
  agent_slug?: string;
  category?: string;
  skip?: number;
  limit?: number;
}

export function useFeedback(filters?: FeedbackFilters) {
  return useQuery({
    queryKey: queryKeys.feedback.all(filters),
    queryFn: () => api.listFeedback(filters),
  });
}

export function useCreateFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      source?: string;
      category?: string;
      content: string;
      user_query?: string;
      agent_slug?: string;
      session_id?: string;
      message_id?: string;
    }) => api.createFeedback(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}

export function useUpdateFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; status?: string; admin_notes?: string }) =>
      api.updateFeedback(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}

export function useDeleteFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteFeedback(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}
