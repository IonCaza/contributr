import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useSSHKeys() {
  return useQuery({ queryKey: queryKeys.sshKeys, queryFn: () => api.listSSHKeys() });
}

export function useCreateSSHKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; key_type: string; rsa_bits?: number }) => api.createSSHKey(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.sshKeys }); },
  });
}

export function useDeleteSSHKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteSSHKey(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.sshKeys }); },
  });
}

export function usePlatformCredentials() {
  return useQuery({ queryKey: queryKeys.platformCredentials, queryFn: () => api.listPlatformCredentials() });
}

export function useCreatePlatformCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; platform: string; token: string; base_url?: string }) =>
      api.createPlatformCredential(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.platformCredentials }); },
  });
}

export function useDeletePlatformCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deletePlatformCredential(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.platformCredentials }); },
  });
}

export function useTestPlatformCredential() {
  return useMutation({
    mutationFn: (id: string) => api.testPlatformCredential(id),
  });
}

export function useUsers() {
  return useQuery({ queryKey: queryKeys.users, queryFn: () => api.listUsers() });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; username: string; password: string; full_name?: string; is_admin?: boolean; send_invite?: boolean; temporary_password?: boolean }) =>
      api.createUser(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.users }); },
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof api.updateUser>[1] }) =>
      api.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.users }); },
  });
}

export function useResetUserMfa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.resetUserMfa(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.users }); },
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.users }); },
  });
}

export function useFileExclusions() {
  return useQuery({ queryKey: queryKeys.fileExclusions, queryFn: () => api.listFileExclusions() });
}

export function useCreateFileExclusion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { pattern: string; description?: string; enabled?: boolean }) => api.createFileExclusion(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.fileExclusions }); },
  });
}

export function useUpdateFileExclusion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { enabled?: boolean; description?: string } }) =>
      api.updateFileExclusion(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.fileExclusions }); },
  });
}

export function useDeleteFileExclusion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteFileExclusion(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.fileExclusions }); },
  });
}

export function useLoadDefaultExclusions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.loadDefaultExclusions(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.fileExclusions }); },
  });
}

export function useAiSettings() {
  return useQuery({ queryKey: queryKeys.aiSettings, queryFn: () => api.getAiSettings() });
}

export function useUpdateAiSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.updateAiSettings>[0]) => api.updateAiSettings(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.aiSettings });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

export function useAiStatus() {
  return useQuery({ queryKey: queryKeys.aiStatus, queryFn: () => api.getAiStatus() });
}

// LLM Providers
export function useLlmProviders() {
  return useQuery({ queryKey: queryKeys.llmProviders, queryFn: () => api.listLlmProviders() });
}

export function useCreateLlmProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createLlmProvider>[0]) => api.createLlmProvider(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.llmProviders });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

export function useUpdateLlmProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof api.updateLlmProvider>[1] }) =>
      api.updateLlmProvider(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.llmProviders });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

export function useDeleteLlmProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteLlmProvider(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.llmProviders });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

// Agents
export function useAgents() {
  return useQuery({ queryKey: queryKeys.agents, queryFn: () => api.listAgents() });
}

export function useCreateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createAgent>[0]) => api.createAgent(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

export function useUpdateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: Parameters<typeof api.updateAgent>[1] }) =>
      api.updateAgent(slug, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.deleteAgent(slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents });
      qc.invalidateQueries({ queryKey: queryKeys.aiStatus });
    },
  });
}

// AI Tools
export function useAiTools() {
  return useQuery({ queryKey: queryKeys.aiTools, queryFn: () => api.listAiTools() });
}

// Knowledge Graphs
export function useKnowledgeGraphs() {
  return useQuery({ queryKey: queryKeys.knowledgeGraphs, queryFn: () => api.listKnowledgeGraphs() });
}

export function useKnowledgeGraph(id: string | null) {
  return useQuery({
    queryKey: queryKeys.knowledgeGraphDetail(id ?? ""),
    queryFn: () => api.getKnowledgeGraph(id!),
    enabled: !!id,
  });
}

export function useCreateKnowledgeGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createKnowledgeGraph>[0]) => api.createKnowledgeGraph(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.knowledgeGraphs }); },
  });
}

export function useUpdateKnowledgeGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof api.updateKnowledgeGraph>[1] }) =>
      api.updateKnowledgeGraph(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.knowledgeGraphs });
    },
  });
}

export function useDeleteKnowledgeGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteKnowledgeGraph(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.knowledgeGraphs }); },
  });
}

export function useRegenerateKnowledgeGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.regenerateKnowledgeGraph(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.knowledgeGraphs });
    },
  });
}

// SMTP Settings
export function useSmtpSettings() {
  return useQuery({ queryKey: queryKeys.smtpSettings, queryFn: () => api.getSmtpSettings() });
}

export function useUpdateSmtpSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.updateSmtpSettings>[0]) => api.updateSmtpSettings(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.smtpSettings }); },
  });
}

export function useTestSmtp() {
  return useMutation({ mutationFn: (data?: { to?: string }) => api.testSmtp(data) });
}

// Email Templates
export function useEmailTemplates() {
  return useQuery({ queryKey: queryKeys.emailTemplates, queryFn: () => api.listEmailTemplates() });
}

export function useUpdateEmailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: { subject?: string; body_html?: string; body_text?: string } }) =>
      api.updateEmailTemplate(slug, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.emailTemplates }); },
  });
}

export function usePreviewEmailTemplate() {
  return useMutation({
    mutationFn: ({ slug, variables }: { slug: string; variables?: Record<string, string> }) =>
      api.previewEmailTemplate(slug, variables),
  });
}

// Auth Settings
export function useAuthSettings() {
  return useQuery({ queryKey: queryKeys.authSettings, queryFn: () => api.getAuthSettings() });
}

export function useUpdateAuthSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.updateAuthSettings>[0]) => api.updateAuthSettings(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.authSettings }); },
  });
}

// OIDC Providers
export function useOidcProviders() {
  return useQuery({ queryKey: queryKeys.oidcProviders, queryFn: () => api.listOidcProviders() });
}

export function useOidcProvider(id: string | null) {
  return useQuery({
    queryKey: queryKeys.oidcProviderDetail(id ?? ""),
    queryFn: () => api.getOidcProvider(id!),
    enabled: !!id,
  });
}

export function useCreateOidcProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createOidcProvider>[0]) => api.createOidcProvider(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.oidcProviders });
      qc.invalidateQueries({ queryKey: queryKeys.authProviders });
    },
  });
}

export function useUpdateOidcProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof api.updateOidcProvider>[1] }) =>
      api.updateOidcProvider(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.oidcProviders });
      qc.invalidateQueries({ queryKey: queryKeys.authProviders });
    },
  });
}

export function useDeleteOidcProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteOidcProvider(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.oidcProviders });
      qc.invalidateQueries({ queryKey: queryKeys.authProviders });
    },
  });
}

export function useDiscoverOidc() {
  return useMutation({
    mutationFn: ({ id, discovery_url }: { id?: string; discovery_url: string }) =>
      id ? api.discoverOidcProvider(id, discovery_url) : api.discoverOidcNew(discovery_url),
  });
}

export function useTestOidcProvider() {
  return useMutation({
    mutationFn: (id: string) => api.testOidcProvider(id),
  });
}

// Auth Providers (public, used on login page)
export function useAuthProviders() {
  return useQuery({
    queryKey: queryKeys.authProviders,
    queryFn: () => api.getAuthProviders(),
  });
}
