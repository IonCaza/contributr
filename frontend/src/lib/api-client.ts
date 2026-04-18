import type {
  LoginResponse, MfaTotpInitResponse, MfaSetupCompleteResponse,
  SmtpSettings, EmailTemplate, AuthSettingsConfig, RecoveryCodesResponse,
  OidcProviderListItem, OidcProvider, OidcProviderCreate, OidcDiscoverResponse,
  AuthProvidersResponse,
  TokenResponse, User, Project, ProjectDetail, ProjectStats,
  Repository, RepoStats, Contributor, ContributorStats, DailyStat,
  SSHKey, SyncJob, TrendData, Branch, PaginatedCommits, ContributorSummary,
  DuplicateGroup, CommitDetail, FileTreeNode, FileDetail, HotspotFile, PRStatItem,
  ChatSession, ChatMessage, AiSettings, AiStatus, FileExclusionPattern,
  PlatformCredential, PlatformCredentialTestResult,
  DiscoveredRepo,
  LlmProvider, AgentConfig, ToolDefinition,
  KnowledgeGraphListItem, KnowledgeGraph,
  Team, TeamMember, DeliveryStats, PaginatedWorkItems, WorkItemsTreeResponse, Iteration,
  DeliveryFilters, FlowMetrics, BacklogHealthMetrics, QualityMetrics,
  IntersectionMetrics, BurndownPoint, SprintDetail, TeamDetail,
  WorkItemDetail, LinkedCommit, WorkItemDetailRow, ContributorDeliverySummary,
  TeamCodeStats, TeamCodeActivity, TeamMemberCodeStats,
  CustomFieldConfig, DiscoveredField,
  DeliverySummary,
  InsightRun, InsightFinding, InsightsSummary,
  ContributorInsightRun, ContributorInsightFinding, ContributorInsightsSummary,
  TeamInsightRun, TeamInsightFinding, TeamInsightsSummary,
  SastScanRun, SastFinding, SastSummary, SastRuleProfile, SastIgnoredRule, SastSettings,
  DepScanRun, DepFinding, DepSummary, DepSettings, PaginatedDepFindings,
  TaskItem,
  AccessPolicy,
  AccessPolicyCreate,
  AccessPolicyUpdate,
} from "./types";

const API_BASE = "/api";

function buildQuery(params: Record<string, string | string[] | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) {
      for (const item of v) sp.append(k, item);
    } else {
      sp.append(k, v);
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

function buildDeliveryQuery(params?: DeliveryFilters): string {
  if (!params) return "";
  return buildQuery({
    iteration_ids: params.iteration_ids,
    from_date: params.from_date,
    to_date: params.to_date,
    team_id: params.team_id,
    contributor_id: params.contributor_id,
  });
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

let refreshPromise: Promise<boolean> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

async function tryRefreshTokens(): Promise<boolean> {
  const rt = typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
  if (!rt) return false;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh?refresh_token=${encodeURIComponent(rt)}`, { method: "POST" });
    if (!res.ok) return false;
    const data: { access_token: string; refresh_token: string } = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && token && !path.startsWith("/auth/")) {
    if (!refreshPromise) {
      refreshPromise = tryRefreshTokens().finally(() => { refreshPromise = null; });
    }
    const refreshed = await refreshPromise;
    if (refreshed) {
      const newToken = getToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } else {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      onSessionExpired?.();
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    let message: string;
    if (Array.isArray(body.detail)) {
      message = body.detail.map((e: { msg?: string; loc?: string[] }) => {
        const field = e.loc?.filter((l) => l !== "body").join(".") || "";
        return field ? `${field}: ${e.msg}` : (e.msg || "Validation error");
      }).join("; ");
    } else {
      message = body.detail || res.statusText;
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // Auth
  register: (data: { email: string; username: string; password: string; full_name?: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data: { username: string; password: string }) =>
    request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  refresh: (refresh_token: string) =>
    request<TokenResponse>(`/auth/refresh?refresh_token=${refresh_token}`, { method: "POST" }),
  me: () => request<User>("/auth/me"),
  updateProfile: (data: { full_name?: string; email?: string }) =>
    request<User>("/auth/me", { method: "PUT", body: JSON.stringify(data) }),
  changeOwnPassword: (data: { current_password: string; new_password: string }) =>
    request<{ detail: string }>("/auth/me/password", { method: "POST", body: JSON.stringify(data) }),
  listUsers: () => request<User[]>("/auth/users"),
  createUser: (data: { email: string; username: string; password: string; full_name?: string; is_admin?: boolean; send_invite?: boolean; temporary_password?: boolean }) =>
    request<User>("/auth/users", { method: "POST", body: JSON.stringify(data) }),
  updateUser: (id: string, data: { email?: string; username?: string; full_name?: string; is_admin?: boolean; is_active?: boolean; password?: string }) =>
    request<User>(`/auth/users/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  resetUserMfa: (id: string) =>
    request<User>(`/auth/users/${id}/mfa/reset`, { method: "POST" }),
  deleteUser: (id: string) => request<void>(`/auth/users/${id}`, { method: "DELETE" }),
  changePassword: (data: { token: string; new_password: string }) =>
    request<TokenResponse>("/auth/change-password", { method: "POST", body: JSON.stringify(data) }),

  // MFA
  mfaVerify: (data: { mfa_token: string; code: string; method: string }) =>
    request<TokenResponse>("/auth/mfa/verify", { method: "POST", body: JSON.stringify(data) }),
  mfaSendEmailOtp: (data: { mfa_token: string }) =>
    request<{ detail: string }>("/auth/mfa/send-email-otp", { method: "POST", body: JSON.stringify(data) }),
  mfaSetupOptions: (token?: string) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return request<{ totp: boolean; email: boolean }>("/auth/mfa/setup/options", { headers });
  },
  mfaTotpInit: (token?: string) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return request<MfaTotpInitResponse>("/auth/mfa/setup/totp/init", { method: "POST", headers });
  },
  mfaTotpConfirm: (data: { secret: string; code: string }, token?: string) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return request<MfaSetupCompleteResponse>("/auth/mfa/setup/totp/confirm", { method: "POST", body: JSON.stringify(data), headers });
  },
  mfaEmailInit: (token?: string) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return request<{ detail: string }>("/auth/mfa/setup/email/init", { method: "POST", headers });
  },
  mfaEmailConfirm: (data: { code: string }, token?: string) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return request<MfaSetupCompleteResponse>("/auth/mfa/setup/email/confirm", { method: "POST", body: JSON.stringify(data), headers });
  },
  mfaDisable: (data: { password: string }) =>
    request<{ detail: string }>("/auth/mfa/disable", { method: "POST", body: JSON.stringify(data) }),
  mfaRegenerateRecoveryCodes: (data: { password: string }) =>
    request<RecoveryCodesResponse>("/auth/mfa/recovery-codes", { method: "POST", body: JSON.stringify(data) }),

  // SMTP Settings
  getSmtpSettings: () => request<SmtpSettings>("/settings/smtp"),
  updateSmtpSettings: (data: Partial<SmtpSettings & { password: string }>) =>
    request<SmtpSettings>("/settings/smtp", { method: "PUT", body: JSON.stringify(data) }),
  testSmtp: (data?: { to?: string }) =>
    request<{ detail: string }>("/settings/smtp/test", { method: "POST", body: JSON.stringify(data ?? {}) }),

  // Email Templates
  listEmailTemplates: () => request<EmailTemplate[]>("/settings/email-templates"),
  getEmailTemplate: (slug: string) => request<EmailTemplate>(`/settings/email-templates/${slug}`),
  updateEmailTemplate: (slug: string, data: { subject?: string; body_html?: string; body_text?: string }) =>
    request<EmailTemplate>(`/settings/email-templates/${slug}`, { method: "PUT", body: JSON.stringify(data) }),
  previewEmailTemplate: (slug: string, variables?: Record<string, string>) =>
    request<{ subject: string; body_html: string }>(`/settings/email-templates/${slug}/preview`, { method: "POST", body: JSON.stringify({ variables }) }),

  // Auth Settings
  getAuthSettings: () => request<AuthSettingsConfig>("/settings/auth"),
  updateAuthSettings: (data: Partial<AuthSettingsConfig>) =>
    request<AuthSettingsConfig>("/settings/auth", { method: "PUT", body: JSON.stringify(data) }),

  // Auth Providers (public)
  getAuthProviders: () => request<AuthProvidersResponse>("/auth/providers"),

  // OIDC Providers (admin)
  listOidcProviders: () => request<OidcProviderListItem[]>("/settings/oidc-providers"),
  getOidcProvider: (id: string) => request<OidcProvider>(`/settings/oidc-providers/${id}`),
  createOidcProvider: (data: OidcProviderCreate) =>
    request<OidcProvider>("/settings/oidc-providers", { method: "POST", body: JSON.stringify(data) }),
  updateOidcProvider: (id: string, data: Partial<OidcProviderCreate>) =>
    request<OidcProvider>(`/settings/oidc-providers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteOidcProvider: (id: string) =>
    request<void>(`/settings/oidc-providers/${id}`, { method: "DELETE" }),
  discoverOidcProvider: (id: string, discovery_url: string) =>
    request<OidcDiscoverResponse>(`/settings/oidc-providers/${id}/discover`, { method: "POST", body: JSON.stringify({ discovery_url }) }),
  discoverOidcNew: (discovery_url: string) =>
    request<OidcDiscoverResponse>("/settings/oidc-providers/discover", { method: "POST", body: JSON.stringify({ discovery_url }) }),
  testOidcProvider: (id: string) =>
    request<Record<string, boolean | string>>(`/settings/oidc-providers/${id}/test`, { method: "POST" }),

  // Projects
  listProjects: () => request<Project[]>("/projects"),
  createProject: (data: { name: string; description?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  updateProject: (id: string, data: { name?: string; description?: string; platform_credential_id?: string | null }) =>
    request<Project>(`/projects/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  getProjectStats: (id: string, params?: { from_date?: string; to_date?: string }) =>
    request<ProjectStats>(`/projects/${id}/stats${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),

  // Repositories
  listRepos: (projectId: string) => request<Repository[]>(`/projects/${projectId}/repositories`),
  createRepo: (projectId: string, data: Record<string, unknown>) =>
    request<Repository>(`/projects/${projectId}/repositories`, { method: "POST", body: JSON.stringify(data) }),
  getRepo: (id: string) => request<Repository>(`/repositories/${id}`),
  updateRepo: (id: string, data: Record<string, unknown>) =>
    request<Repository>(`/repositories/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteRepo: (id: string) => request<void>(`/repositories/${id}`, { method: "DELETE" }),
  purgeRepoData: (id: string) => request<{ status: string; repository_id: string }>(`/repositories/${id}/purge-data`, { method: "POST" }),
  syncRepo: (id: string) => request<SyncJob>(`/repositories/${id}/sync`, { method: "POST" }),
  cancelSyncJob: (repoId: string, jobId: string) =>
    request<SyncJob>(`/repositories/${repoId}/sync-jobs/${jobId}/cancel`, { method: "POST" }),
  getRepoStats: (id: string, params?: { branches?: string[]; from_date?: string; to_date?: string }) =>
    request<RepoStats>(`/repositories/${id}/stats${buildQuery({ branch: params?.branches, from_date: params?.from_date, to_date: params?.to_date })}`),
  listSyncJobs: (id: string) => request<SyncJob[]>(`/repositories/${id}/sync-jobs`),
  listBranches: (repoId: string, contributorId?: string) =>
    request<Branch[]>(`/repositories/${repoId}/branches${buildQuery({ contributor_id: contributorId })}`),
  listRepoContributors: (repoId: string, branches?: string[]) =>
    request<ContributorSummary[]>(`/repositories/${repoId}/contributors${buildQuery({ branch: branches })}`),
  listRepoCommits: (repoId: string, params?: { branch?: string[]; contributor_id?: string; search?: string; page?: number; per_page?: number }) =>
    request<PaginatedCommits>(`/commits/by-repo/${repoId}${buildQuery({
      branch: params?.branch,
      contributor_id: params?.contributor_id,
      search: params?.search,
      page: params?.page?.toString(),
      per_page: params?.per_page?.toString(),
    })}`),
  listContributorCommits: (contributorId: string, params?: { repository_id?: string; branch?: string[]; from_date?: string; to_date?: string; search?: string; page?: number; per_page?: number }) =>
    request<PaginatedCommits>(`/commits/by-contributor/${contributorId}${buildQuery({
      repository_id: params?.repository_id,
      branch: params?.branch,
      from_date: params?.from_date,
      to_date: params?.to_date,
      search: params?.search,
      page: params?.page?.toString(),
      per_page: params?.per_page?.toString(),
    })}`),

  // Contributors
  listContributors: (projectId?: string) =>
    request<Contributor[]>(`/contributors${projectId ? `?project_id=${projectId}` : ""}`),
  getContributor: (id: string) => request<Contributor>(`/contributors/${id}`),
  mergeContributors: (sourceId: string, targetId: string) =>
    request<{ merged: boolean }>(`/contributors/${sourceId}/merge`, { method: "POST", body: JSON.stringify({ merge_into_id: targetId }) }),
  getDuplicateContributors: () => request<DuplicateGroup[]>("/contributors/duplicates"),
  getContributorStats: (id: string, params?: { from_date?: string; to_date?: string; repository_id?: string; branch?: string[] }) =>
    request<ContributorStats>(`/contributors/${id}/stats${buildQuery({
      from_date: params?.from_date,
      to_date: params?.to_date,
      repository_id: params?.repository_id,
      branch: params?.branch,
    })}`),
  getContributorRepos: (id: string) => request<{ id: string; name: string; platform: string }[]>(`/contributors/${id}/repositories`),

  // Stats
  dailyStats: (params: Record<string, string | string[] | undefined>) =>
    request<DailyStat[]>(`/stats/daily${buildQuery(params)}`),
  weeklyStats: (params: Record<string, string | string[] | undefined>) =>
    request<DailyStat[]>(`/stats/weekly${buildQuery(params)}`),
  monthlyStats: (params: Record<string, string | string[] | undefined>) =>
    request<DailyStat[]>(`/stats/monthly${buildQuery(params)}`),
  trends: (params: Record<string, string | string[] | undefined>) =>
    request<TrendData>(`/stats/trends${buildQuery(params)}`),
  deliverySummary: () => request<DeliverySummary>("/stats/delivery-summary"),

  getCommitDetail: (id: string) => request<CommitDetail>(`/commits/${id}`),

  // File tree & ownership
  getFileTree: (repoId: string, branch?: string) =>
    request<FileTreeNode[]>(`/repositories/${repoId}/file-tree${buildQuery({ branch })}`),
  getFileDetail: (repoId: string, path: string, branch?: string) =>
    request<FileDetail>(`/repositories/${repoId}/files/${encodeURIComponent(path)}${buildQuery({ branch })}`),
  getHotspots: (repoId: string, limit?: number, branch?: string) =>
    request<HotspotFile[]>(`/repositories/${repoId}/hotspots${buildQuery({ limit: limit?.toString(), branch })}`),

  // PR stats
  getProjectPRStats: (projectId: string) => request<PRStatItem[]>(`/projects/${projectId}/pr-stats`),

  // SSH Keys
  listSSHKeys: () => request<SSHKey[]>("/ssh-keys"),
  createSSHKey: (data: { name: string; key_type: string; rsa_bits?: number }) =>
    request<SSHKey>("/ssh-keys", { method: "POST", body: JSON.stringify(data) }),
  deleteSSHKey: (id: string) => request<void>(`/ssh-keys/${id}`, { method: "DELETE" }),

  // Platform Credentials
  listPlatformCredentials: () => request<PlatformCredential[]>("/platform-credentials"),
  createPlatformCredential: (data: { name: string; platform: string; token: string; base_url?: string }) =>
    request<PlatformCredential>("/platform-credentials", { method: "POST", body: JSON.stringify(data) }),
  deletePlatformCredential: (id: string) => request<void>(`/platform-credentials/${id}`, { method: "DELETE" }),
  testPlatformCredential: (id: string) =>
    request<PlatformCredentialTestResult>(`/platform-credentials/${id}/test`, { method: "POST" }),
  discoverRepos: (credentialId: string, projectName: string) =>
    request<DiscoveredRepo[]>(`/platform-credentials/${credentialId}/discover-repos`, {
      method: "POST", body: JSON.stringify({ project_name: projectName }),
    }),

  // Backup
  exportBackup: async (): Promise<Blob> => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/backup/export`, { headers });
    if (!res.ok) throw new ApiError(res.status, "Export failed");
    return res.blob();
  },
  importBackup: async (file: File): Promise<{ counts: Record<string, { submitted: number; imported: number }> }> => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/backup/import`, { method: "POST", headers, body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  },

  // AI Settings
  listFileExclusions: () => request<FileExclusionPattern[]>("/file-exclusions"),
  createFileExclusion: (data: { pattern: string; description?: string; enabled?: boolean }) =>
    request<FileExclusionPattern>("/file-exclusions", { method: "POST", body: JSON.stringify(data) }),
  updateFileExclusion: (id: string, data: { enabled?: boolean; description?: string }) =>
    request<FileExclusionPattern>(`/file-exclusions/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteFileExclusion: (id: string) =>
    request<void>(`/file-exclusions/${id}`, { method: "DELETE" }),
  loadDefaultExclusions: () =>
    request<{ added: number }>("/file-exclusions/load-defaults", { method: "POST" }),

  getAiSettings: () => request<AiSettings>("/ai/settings"),
  updateAiSettings: (data: Partial<AiSettings>) =>
    request<AiSettings>("/ai/settings", { method: "PUT", body: JSON.stringify(data) }),
  getAiStatus: () => request<AiStatus>("/ai/settings/status"),

  // LLM Providers
  listLlmProviders: () => request<LlmProvider[]>("/ai/llm-providers"),
  createLlmProvider: (data: { name: string; provider_type?: string; model: string; model_type?: string; api_key?: string; base_url?: string; temperature?: number; context_window?: number | null; is_default?: boolean }) =>
    request<LlmProvider>("/ai/llm-providers", { method: "POST", body: JSON.stringify(data) }),
  updateLlmProvider: (id: string, data: { name?: string; provider_type?: string; model?: string; model_type?: string; api_key?: string; base_url?: string; temperature?: number; context_window?: number | null; is_default?: boolean }) =>
    request<LlmProvider>(`/ai/llm-providers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteLlmProvider: (id: string) => request<void>(`/ai/llm-providers/${id}`, { method: "DELETE" }),

  // Agents
  listAgents: () => request<AgentConfig[]>("/ai/agents"),
  getAgent: (slug: string) => request<AgentConfig>(`/ai/agents/${slug}`),
  createAgent: (data: { slug: string; name: string; description?: string; agent_type?: string; llm_provider_id?: string; system_prompt?: string; max_iterations?: number; summary_token_limit?: number | null; enabled?: boolean; tool_slugs?: string[]; knowledge_graph_ids?: string[]; member_agent_ids?: string[] }) =>
    request<AgentConfig>("/ai/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (slug: string, data: { name?: string; description?: string; agent_type?: string; llm_provider_id?: string; system_prompt?: string; max_iterations?: number; summary_token_limit?: number | null; enabled?: boolean; tool_slugs?: string[]; knowledge_graph_ids?: string[]; member_agent_ids?: string[] }) =>
    request<AgentConfig>(`/ai/agents/${slug}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (slug: string) => request<void>(`/ai/agents/${slug}`, { method: "DELETE" }),

  // AI Tools (read-only registry)
  listAiTools: () => request<ToolDefinition[]>("/ai/tools"),

  // Knowledge Graphs
  listKnowledgeGraphs: () => request<KnowledgeGraphListItem[]>("/ai/knowledge-graphs"),
  getKnowledgeGraph: (id: string) => request<KnowledgeGraph>(`/ai/knowledge-graphs/${id}`),
  createKnowledgeGraph: (data: { name: string; description?: string; generation_mode?: string }) =>
    request<KnowledgeGraph>("/ai/knowledge-graphs", { method: "POST", body: JSON.stringify(data) }),
  updateKnowledgeGraph: (id: string, data: { name?: string; description?: string; content?: string; excluded_entities?: string[] }) =>
    request<KnowledgeGraph>(`/ai/knowledge-graphs/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteKnowledgeGraph: (id: string) => request<void>(`/ai/knowledge-graphs/${id}`, { method: "DELETE" }),
  regenerateKnowledgeGraph: (id: string) =>
    request<KnowledgeGraph>(`/ai/knowledge-graphs/${id}/regenerate`, { method: "POST" }),

  // Chat
  listChatSessions: () => request<ChatSession[]>("/chat/sessions"),
  getChatSessionMessages: (id: string) => request<ChatMessage[]>(`/chat/sessions/${id}`),
  createChatSession: () => request<ChatSession>("/chat/sessions", { method: "POST" }),
  renameChatSession: (id: string, title: string) =>
    request<ChatSession>(`/chat/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  archiveChatSession: (id: string) =>
    request<ChatSession>(`/chat/sessions/${id}/archive`, { method: "POST" }),
  unarchiveChatSession: (id: string) =>
    request<ChatSession>(`/chat/sessions/${id}/unarchive`, { method: "POST" }),
  deleteChatSession: (id: string) => request<void>(`/chat/sessions/${id}`, { method: "DELETE" }),
  getSessionTasks: (sessionId: string) =>
    request<TaskItem[]>(`/chat/sessions/${sessionId}/tasks`),

  // Teams
  listTeams: (projectId?: string) =>
    request<Team[]>(`/teams${buildQuery({ project_id: projectId })}`),
  getTeam: (id: string) => request<Team>(`/teams/${id}`),
  createTeam: (data: { project_id: string; name: string; description?: string }) =>
    request<Team>("/teams", { method: "POST", body: JSON.stringify(data) }),
  updateTeam: (id: string, data: { name?: string; description?: string }) =>
    request<Team>(`/teams/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTeam: (id: string) => request<void>(`/teams/${id}`, { method: "DELETE" }),
  listTeamMembers: (teamId: string) => request<TeamMember[]>(`/teams/${teamId}/members`),
  addTeamMember: (teamId: string, data: { contributor_id: string; role?: string }) =>
    request<{ status: string }>(`/teams/${teamId}/members`, { method: "POST", body: JSON.stringify(data) }),
  removeTeamMember: (teamId: string, contributorId: string) =>
    request<void>(`/teams/${teamId}/members/${contributorId}`, { method: "DELETE" }),

  // Delivery
  getDeliveryStats: (projectId: string, params?: DeliveryFilters) =>
    request<DeliveryStats>(`/projects/${projectId}/delivery/stats${buildDeliveryQuery(params)}`),
  listWorkItems: (projectId: string, params?: {
    work_item_type?: string;
    state?: string;
    assignee_id?: string;
    iteration_ids?: string[];
    parent_id?: string;
    search?: string;
    from_date?: string;
    to_date?: string;
    resolved_from?: string;
    resolved_to?: string;
    closed_from?: string;
    closed_to?: string;
    priority?: number;
    story_points_min?: number;
    story_points_max?: number;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  }) =>
    request<PaginatedWorkItems>(`/projects/${projectId}/delivery/work-items${buildQuery({
      work_item_type: params?.work_item_type,
      state: params?.state,
      assignee_id: params?.assignee_id,
      iteration_ids: params?.iteration_ids,
      parent_id: params?.parent_id,
      search: params?.search,
      from_date: params?.from_date,
      to_date: params?.to_date,
      resolved_from: params?.resolved_from,
      resolved_to: params?.resolved_to,
      closed_from: params?.closed_from,
      closed_to: params?.closed_to,
      priority: params?.priority?.toString(),
      story_points_min: params?.story_points_min?.toString(),
      story_points_max: params?.story_points_max?.toString(),
      sort_by: params?.sort_by,
      sort_order: params?.sort_order,
      page: params?.page?.toString(),
      page_size: params?.page_size?.toString(),
    })}`),
  getWorkItemsTree: (projectId: string, params?: {
    work_item_type?: string;
    state?: string;
    assignee_id?: string;
    iteration_ids?: string[];
    search?: string;
    from_date?: string;
    to_date?: string;
    resolved_from?: string;
    resolved_to?: string;
    closed_from?: string;
    closed_to?: string;
    priority?: number;
    story_points_min?: number;
    story_points_max?: number;
    sort_by?: string;
    sort_order?: string;
    max_items?: number;
  }) =>
    request<WorkItemsTreeResponse>(`/projects/${projectId}/delivery/work-items/tree${buildQuery({
      work_item_type: params?.work_item_type,
      state: params?.state,
      assignee_id: params?.assignee_id,
      iteration_ids: params?.iteration_ids,
      search: params?.search,
      from_date: params?.from_date,
      to_date: params?.to_date,
      resolved_from: params?.resolved_from,
      resolved_to: params?.resolved_to,
      closed_from: params?.closed_from,
      closed_to: params?.closed_to,
      priority: params?.priority?.toString(),
      story_points_min: params?.story_points_min?.toString(),
      story_points_max: params?.story_points_max?.toString(),
      sort_by: params?.sort_by,
      sort_order: params?.sort_order,
      max_items: params?.max_items?.toString(),
    })}`),
  getWorkItem: (projectId: string, workItemId: string) =>
    request<unknown>(`/projects/${projectId}/delivery/work-items/${workItemId}`),
  listIterations: (projectId: string) =>
    request<Iteration[]>(`/projects/${projectId}/delivery/iterations`),
  getIteration: (projectId: string, iterationId: string) =>
    request<Iteration>(`/projects/${projectId}/delivery/iterations/${iterationId}`),
  getVelocity: (projectId: string, params?: { limit?: number; iteration_ids?: string[] }) =>
    request<{ iteration: string; points: number }[]>(`/projects/${projectId}/delivery/velocity${buildQuery({ limit: params?.limit?.toString(), iteration_id: params?.iteration_ids })}`),
  getDeliveryTrends: (projectId: string, days?: number) =>
    request<{ date: string; created: number; completed: number }[]>(`/projects/${projectId}/delivery/trends${buildQuery({ days: days?.toString() })}`),
  getFlowMetrics: (projectId: string, params?: DeliveryFilters) =>
    request<FlowMetrics>(`/projects/${projectId}/delivery/metrics/flow${buildDeliveryQuery(params)}`),
  getBacklogHealth: (projectId: string, params?: DeliveryFilters) =>
    request<BacklogHealthMetrics>(`/projects/${projectId}/delivery/metrics/backlog-health${buildDeliveryQuery(params)}`),
  getQualityMetrics: (projectId: string, params?: DeliveryFilters) =>
    request<QualityMetrics>(`/projects/${projectId}/delivery/metrics/quality${buildDeliveryQuery(params)}`),
  getIntersectionMetrics: (projectId: string, params?: DeliveryFilters) =>
    request<IntersectionMetrics>(`/projects/${projectId}/delivery/intersection${buildDeliveryQuery(params)}`),
  getItemDetails: (projectId: string, params?: DeliveryFilters) =>
    request<WorkItemDetailRow[]>(`/projects/${projectId}/delivery/metrics/item-details${buildDeliveryQuery(params)}`),
  getContributorSummary: (projectId: string, params?: DeliveryFilters) =>
    request<ContributorDeliverySummary[]>(`/projects/${projectId}/delivery/metrics/contributor-summary${buildDeliveryQuery(params)}`),
  getWorkItemDetail: (projectId: string, workItemId: string) =>
    request<WorkItemDetail>(`/projects/${projectId}/delivery/work-items/${workItemId}`),
  updateWorkItem: (projectId: string, workItemId: string, data: { description?: string; title?: string }) =>
    request<WorkItemDetail>(`/projects/${projectId}/delivery/work-items/${workItemId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  pullWorkItem: (projectId: string, workItemId: string) =>
    request<WorkItemDetail>(`/projects/${projectId}/delivery/work-items/${workItemId}/pull`, {
      method: "POST",
    }),
  acceptWorkItemDraft: (projectId: string, workItemId: string) =>
    request<WorkItemDetail>(`/projects/${projectId}/delivery/work-items/${workItemId}/accept-draft`, {
      method: "POST",
    }),
  discardWorkItemDraft: (projectId: string, workItemId: string) =>
    request<void>(`/projects/${projectId}/delivery/work-items/${workItemId}/discard-draft`, {
      method: "POST",
    }),
  getWorkItemCommits: (projectId: string, workItemId: string) =>
    request<LinkedCommit[]>(`/projects/${projectId}/delivery/work-items/${workItemId}/commits`),
  getWorkItemActivities: (projectId: string, workItemId: string, params?: { page?: number; page_size?: number }) =>
    request<import("./types").PaginatedActivities>(
      `/projects/${projectId}/delivery/work-items/${workItemId}/activities${buildQuery({
        page: params?.page?.toString(),
        page_size: params?.page_size?.toString(),
      })}`,
    ),
  getContributorActivities: (projectId: string, contributorId: string, params?: { page?: number; page_size?: number }) =>
    request<import("./types").PaginatedContributorActivities>(
      `/projects/${projectId}/delivery/activities/contributor/${contributorId}${buildQuery({
        page: params?.page?.toString(),
        page_size: params?.page_size?.toString(),
      })}`,
    ),
  getContributorActivityMetrics: (projectId: string, contributorId: string, params?: { from_date?: string; to_date?: string }) =>
    request<import("./types").ContributorActivityMetrics>(
      `/projects/${projectId}/delivery/activities/contributor/${contributorId}/metrics${buildQuery({
        from_date: params?.from_date,
        to_date: params?.to_date,
      })}`,
    ),
  getSprintDetail: (projectId: string, iterationId: string) =>
    request<SprintDetail>(`/projects/${projectId}/delivery/iterations/${iterationId}`),
  getSprintBurndown: (projectId: string, iterationId: string) =>
    request<BurndownPoint[]>(`/projects/${projectId}/delivery/iterations/${iterationId}/burndown`),
  getTeamDetail: (projectId: string, teamId: string) =>
    request<TeamDetail>(`/projects/${projectId}/delivery/teams/${teamId}`),
  listDeliveryTeams: (projectId: string) =>
    request<TeamDetail[]>(`/projects/${projectId}/delivery/teams`),
  triggerDeliverySync: (projectId: string) =>
    request<{ task_id: string; job_id: string; status: string }>(`/projects/${projectId}/delivery/sync`, { method: "POST" }),
  purgeDelivery: (projectId: string) =>
    request<{ status: string; project_id: string }>(`/projects/${projectId}/delivery/purge`, { method: "POST" }),
  listDeliverySyncJobs: (projectId: string) =>
    request<{ id: string; status: string; started_at: string | null; finished_at: string | null; error_message: string | null; created_at: string }[]>(`/projects/${projectId}/delivery/sync-jobs`),
  getDeliverySyncLogUrl: (projectId: string) =>
    `${API_BASE}/projects/${projectId}/delivery/sync/logs`,

  // Custom Fields
  discoverCustomFields: (projectId: string) =>
    request<DiscoveredField[]>(`/projects/${projectId}/custom-fields/discover`),
  listCustomFields: (projectId: string) =>
    request<CustomFieldConfig[]>(`/projects/${projectId}/custom-fields`),
  bulkUpsertCustomFields: (projectId: string, fields: { field_reference_name: string; display_name: string; field_type: string; enabled: boolean }[]) =>
    request<CustomFieldConfig[]>(`/projects/${projectId}/custom-fields`, { method: "PUT", body: JSON.stringify({ fields }) }),
  deleteCustomField: (projectId: string, configId: string) =>
    request<void>(`/projects/${projectId}/custom-fields/${configId}`, { method: "DELETE" }),

  // Insights
  listInsightFindings: (projectId: string, params?: { category?: string; severity?: string; status?: string }) =>
    request<InsightFinding[]>(`/projects/${projectId}/insights${buildQuery({
      category: params?.category,
      severity: params?.severity,
      status: params?.status,
    })}`),
  getInsightsSummary: (projectId: string) =>
    request<InsightsSummary>(`/projects/${projectId}/insights/summary`),
  listInsightRuns: (projectId: string) =>
    request<InsightRun[]>(`/projects/${projectId}/insights/runs`),
  triggerInsightRun: (projectId: string) =>
    request<InsightRun>(`/projects/${projectId}/insights/run`, { method: "POST" }),
  dismissInsightFinding: (projectId: string, findingId: string) =>
    request<InsightFinding>(`/projects/${projectId}/insights/${findingId}/dismiss`, { method: "PATCH" }),

  // Team Analytics
  getTeamCodeStats: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<TeamCodeStats>(`/projects/${projectId}/teams/${teamId}/analytics/code${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamCodeActivity: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<TeamCodeActivity[]>(`/projects/${projectId}/teams/${teamId}/analytics/code/activity${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamMemberStats: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<TeamMemberCodeStats[]>(`/projects/${projectId}/teams/${teamId}/analytics/code/members${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamDeliveryStats: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<DeliveryStats>(`/projects/${projectId}/teams/${teamId}/analytics/delivery${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamDeliveryVelocity: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<{ iteration: string; points: number }[]>(`/projects/${projectId}/teams/${teamId}/analytics/delivery/velocity${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamDeliveryFlow: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<FlowMetrics>(`/projects/${projectId}/teams/${teamId}/analytics/delivery/flow${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamDeliveryBacklog: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<BacklogHealthMetrics>(`/projects/${projectId}/teams/${teamId}/analytics/delivery/backlog${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamDeliveryQuality: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<QualityMetrics>(`/projects/${projectId}/teams/${teamId}/analytics/delivery/quality${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamDeliveryIntersection: (projectId: string, teamId: string, params?: { from_date?: string; to_date?: string }) =>
    request<IntersectionMetrics>(`/projects/${projectId}/teams/${teamId}/analytics/delivery/intersection${buildQuery({ from_date: params?.from_date, to_date: params?.to_date })}`),
  getTeamWorkItems: (projectId: string, teamId: string, params?: { state?: string; search?: string; page?: number; page_size?: number }) =>
    request<PaginatedWorkItems>(`/projects/${projectId}/teams/${teamId}/analytics/delivery/work-items${buildQuery({
      state: params?.state,
      search: params?.search,
      page: params?.page?.toString(),
      page_size: params?.page_size?.toString(),
    })}`),
  getTeamInsights: (projectId: string, teamId: string) =>
    request<InsightFinding[]>(`/projects/${projectId}/teams/${teamId}/analytics/insights`),

  // Contributor Insights
  listContributorInsightFindings: (contributorId: string, params?: { category?: string; severity?: string; status?: string }) =>
    request<ContributorInsightFinding[]>(`/contributors/${contributorId}/insights${buildQuery({
      category: params?.category,
      severity: params?.severity,
      status: params?.status,
    })}`),
  getContributorInsightsSummary: (contributorId: string) =>
    request<ContributorInsightsSummary>(`/contributors/${contributorId}/insights/summary`),
  listContributorInsightRuns: (contributorId: string) =>
    request<ContributorInsightRun[]>(`/contributors/${contributorId}/insights/runs`),
  triggerContributorInsightRun: (contributorId: string) =>
    request<ContributorInsightRun>(`/contributors/${contributorId}/insights/run`, { method: "POST" }),
  dismissContributorInsightFinding: (contributorId: string, findingId: string) =>
    request<ContributorInsightFinding>(`/contributors/${contributorId}/insights/${findingId}/dismiss`, { method: "PATCH" }),

  // Team Insights
  listTeamInsightFindings: (projectId: string, teamId: string, params?: { category?: string; severity?: string; status?: string }) =>
    request<TeamInsightFinding[]>(`/projects/${projectId}/teams/${teamId}/insights${buildQuery({
      category: params?.category,
      severity: params?.severity,
      status: params?.status,
    })}`),
  getTeamInsightsSummary: (projectId: string, teamId: string) =>
    request<TeamInsightsSummary>(`/projects/${projectId}/teams/${teamId}/insights/summary`),
  listTeamInsightRuns: (projectId: string, teamId: string) =>
    request<TeamInsightRun[]>(`/projects/${projectId}/teams/${teamId}/insights/runs`),
  triggerTeamInsightRun: (projectId: string, teamId: string) =>
    request<TeamInsightRun>(`/projects/${projectId}/teams/${teamId}/insights/run`, { method: "POST" }),
  dismissTeamInsightFinding: (projectId: string, teamId: string, findingId: string) =>
    request<TeamInsightFinding>(`/projects/${projectId}/teams/${teamId}/insights/${findingId}/dismiss`, { method: "PATCH" }),

  // SAST
  triggerSastScan: (repoId: string, data?: { branch?: string; profile_id?: string }) =>
    request<SastScanRun>(`/repositories/${repoId}/sast/scan`, { method: "POST", body: JSON.stringify(data || {}) }),
  listSastFindings: (repoId: string, params?: { severity?: string; status?: string; file_path?: string; rule_id?: string }) =>
    request<SastFinding[]>(`/repositories/${repoId}/sast/findings${buildQuery({
      severity: params?.severity,
      status: params?.status,
      file_path: params?.file_path,
      rule_id: params?.rule_id,
    })}`),
  getSastSummary: (repoId: string) =>
    request<SastSummary>(`/repositories/${repoId}/sast/summary`),
  listSastRuns: (repoId: string) =>
    request<SastScanRun[]>(`/repositories/${repoId}/sast/runs`),
  dismissSastFinding: (repoId: string, findingId: string) =>
    request<SastFinding>(`/repositories/${repoId}/sast/findings/${findingId}/dismiss`, { method: "PATCH" }),
  markSastFalsePositive: (repoId: string, findingId: string) =>
    request<SastFinding>(`/repositories/${repoId}/sast/findings/${findingId}/false-positive`, { method: "PATCH" }),

  listProjectSastFindings: (projectId: string, params?: { severity?: string; status?: string; file_path?: string; rule_id?: string }) =>
    request<SastFinding[]>(`/projects/${projectId}/sast/findings${buildQuery({
      severity: params?.severity,
      status: params?.status,
      file_path: params?.file_path,
      rule_id: params?.rule_id,
    })}`),
  getProjectSastSummary: (projectId: string) =>
    request<SastSummary>(`/projects/${projectId}/sast/summary`),
  listProjectSastRuns: (projectId: string) =>
    request<SastScanRun[]>(`/projects/${projectId}/sast/runs`),

  listSastProfiles: () => request<SastRuleProfile[]>("/sast/profiles"),
  createSastProfile: (data: { name: string; description?: string; rulesets?: string[]; custom_rules_yaml?: string; is_default?: boolean }) =>
    request<SastRuleProfile>("/sast/profiles", { method: "POST", body: JSON.stringify(data) }),
  updateSastProfile: (id: string, data: { name?: string; description?: string; rulesets?: string[]; custom_rules_yaml?: string; is_default?: boolean }) =>
    request<SastRuleProfile>(`/sast/profiles/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSastProfile: (id: string) => request<void>(`/sast/profiles/${id}`, { method: "DELETE" }),

  getSastSettings: () => request<SastSettings>("/sast/settings"),
  updateSastSettings: (data: { auto_sast_on_sync: boolean }) =>
    request<SastSettings>("/sast/settings", { method: "PUT", body: JSON.stringify(data) }),

  // SAST Ignored Rules
  listGlobalIgnoredRules: () => request<SastIgnoredRule[]>("/sast/ignored-rules"),
  addGlobalIgnoredRule: (data: { rule_id: string; reason?: string }) =>
    request<SastIgnoredRule>("/sast/ignored-rules", { method: "POST", body: JSON.stringify(data) }),
  removeGlobalIgnoredRule: (id: string) => request<void>(`/sast/ignored-rules/${id}`, { method: "DELETE" }),
  listRepoIgnoredRules: (repoId: string) => request<SastIgnoredRule[]>(`/repositories/${repoId}/sast/ignored-rules`),
  addRepoIgnoredRule: (repoId: string, data: { rule_id: string; reason?: string }) =>
    request<SastIgnoredRule>(`/repositories/${repoId}/sast/ignored-rules`, { method: "POST", body: JSON.stringify(data) }),
  removeRepoIgnoredRule: (repoId: string, id: string) =>
    request<void>(`/repositories/${repoId}/sast/ignored-rules/${id}`, { method: "DELETE" }),

  // SAST Reports
  getSastReportUrl: (repoId: string, format: string) =>
    `${API_BASE}/repositories/${repoId}/sast/report?format=${format}`,
  getProjectSastReportUrl: (projectId: string, format: string) =>
    `${API_BASE}/projects/${projectId}/sast/report?format=${format}`,

  // Dependencies (SCA)
  triggerDepScan: (repoId: string) =>
    request<DepScanRun>(`/repositories/${repoId}/dependencies/scan`, { method: "POST", body: JSON.stringify({}) }),
  listDepFindings: (repoId: string, params?: { severity?: string; ecosystem?: string; outdated?: boolean; vulnerable?: boolean; status?: string; file_path?: string; search?: string; page?: number; page_size?: number }) =>
    request<PaginatedDepFindings>(`/repositories/${repoId}/dependencies/findings${buildQuery({
      severity: params?.severity,
      ecosystem: params?.ecosystem,
      outdated: params?.outdated?.toString(),
      vulnerable: params?.vulnerable?.toString(),
      status: params?.status,
      file_path: params?.file_path,
      search: params?.search,
      page: params?.page?.toString(),
      page_size: params?.page_size?.toString(),
    })}`),
  getDepSummary: (repoId: string) =>
    request<DepSummary>(`/repositories/${repoId}/dependencies/summary`),
  listDepRuns: (repoId: string) =>
    request<DepScanRun[]>(`/repositories/${repoId}/dependencies/runs`),
  dismissDepFinding: (repoId: string, findingId: string) =>
    request<DepFinding>(`/repositories/${repoId}/dependencies/findings/${findingId}/dismiss`, { method: "PATCH" }),

  listProjectDepFindings: (projectId: string, params?: { severity?: string; ecosystem?: string; outdated?: boolean; vulnerable?: boolean; status?: string; file_path?: string; search?: string; page?: number; page_size?: number }) =>
    request<PaginatedDepFindings>(`/projects/${projectId}/dependencies/findings${buildQuery({
      severity: params?.severity,
      ecosystem: params?.ecosystem,
      outdated: params?.outdated?.toString(),
      vulnerable: params?.vulnerable?.toString(),
      status: params?.status,
      file_path: params?.file_path,
      search: params?.search,
      page: params?.page?.toString(),
      page_size: params?.page_size?.toString(),
    })}`),
  getProjectDepSummary: (projectId: string) =>
    request<DepSummary>(`/projects/${projectId}/dependencies/summary`),
  listProjectDepRuns: (projectId: string) =>
    request<DepScanRun[]>(`/projects/${projectId}/dependencies/runs`),

  getDepSettings: () => request<DepSettings>("/dependencies/settings"),
  updateDepSettings: (data: { auto_dep_scan_on_sync: boolean }) =>
    request<DepSettings>("/dependencies/settings", { method: "PUT", body: JSON.stringify(data) }),

  getDepReportUrl: (repoId: string, format: string) =>
    `${API_BASE}/repositories/${repoId}/dependencies/report?format=${format}`,
  getProjectDepReportUrl: (projectId: string, format: string) =>
    `${API_BASE}/projects/${projectId}/dependencies/report?format=${format}`,

  // Feedback
  listFeedback: (params?: { source?: string; status?: string; agent_slug?: string; category?: string; skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.source) qs.set("source", params.source);
    if (params?.status) qs.set("status", params.status);
    if (params?.agent_slug) qs.set("agent_slug", params.agent_slug);
    if (params?.category) qs.set("category", params.category);
    if (params?.skip !== undefined) qs.set("skip", String(params.skip));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<import("./types").PaginatedFeedback>(`/feedback${q ? `?${q}` : ""}`);
  },
  createFeedback: (data: { source?: string; category?: string; content: string; user_query?: string; agent_slug?: string; session_id?: string; message_id?: string }) =>
    request<import("./types").FeedbackItem>("/feedback", { method: "POST", body: JSON.stringify(data) }),
  updateFeedback: (id: string, data: { status?: string; admin_notes?: string }) =>
    request<import("./types").FeedbackItem>(`/feedback/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteFeedback: (id: string) => request<void>(`/feedback/${id}`, { method: "DELETE" }),

  // Pull Requests
  listPullRequests: (projectId: string, params?: {
    state?: string; repository_id?: string; contributor_id?: string;
    reviewer_id?: string; from_date?: string; to_date?: string;
    search?: string; sort_by?: string; sort_dir?: string;
    page?: number; page_size?: number;
  }) => request<import("./types").PRListResponse>(
    `/projects/${projectId}/pull-requests${buildQuery({
      state: params?.state,
      repository_id: params?.repository_id,
      contributor_id: params?.contributor_id,
      reviewer_id: params?.reviewer_id,
      from_date: params?.from_date,
      to_date: params?.to_date,
      search: params?.search,
      sort_by: params?.sort_by,
      sort_dir: params?.sort_dir,
      page: params?.page?.toString(),
      page_size: params?.page_size?.toString(),
    })}`
  ),
  getPullRequest: (projectId: string, prId: string) =>
    request<import("./types").PRDetail>(`/projects/${projectId}/pull-requests/${prId}`),
  syncPullRequest: (projectId: string, prId: string) =>
    request<import("./types").PRDetail>(`/projects/${projectId}/pull-requests/${prId}/sync`, { method: "POST" }),
  getPRAnalytics: (projectId: string, params?: {
    from_date?: string; to_date?: string; repository_id?: string;
  }) => request<import("./types").PRAnalytics>(
    `/projects/${projectId}/pull-requests/analytics${buildQuery({
      from_date: params?.from_date,
      to_date: params?.to_date,
      repository_id: params?.repository_id,
    })}`
  ),

  // ADRs
  getAdrConfig: (projectId: string) =>
    request<import("./types").AdrConfig>(`/projects/${projectId}/adrs/config`),
  updateAdrConfig: (projectId: string, data: { repository_id?: string | null; directory_path?: string; naming_convention?: string }) =>
    request<import("./types").AdrConfig>(`/projects/${projectId}/adrs/config`, { method: "PUT", body: JSON.stringify(data) }),
  syncAdrs: (projectId: string) =>
    request<{ synced: number }>(`/projects/${projectId}/adrs/config/sync`, { method: "POST" }),
  listAdrTemplates: (projectId: string) =>
    request<import("./types").AdrTemplate[]>(`/projects/${projectId}/adrs/templates`),
  createAdrTemplate: (projectId: string, data: { name: string; description?: string; content: string; is_default?: boolean }) =>
    request<import("./types").AdrTemplate>(`/projects/${projectId}/adrs/templates`, { method: "POST", body: JSON.stringify(data) }),
  updateAdrTemplate: (projectId: string, id: string, data: { name?: string; description?: string; content?: string; is_default?: boolean }) =>
    request<import("./types").AdrTemplate>(`/projects/${projectId}/adrs/templates/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAdrTemplate: (projectId: string, id: string) =>
    request<void>(`/projects/${projectId}/adrs/templates/${id}`, { method: "DELETE" }),
  listAdrs: (projectId: string, params?: { status?: string; search?: string; sort_by?: string }) =>
    request<import("./types").Adr[]>(`/projects/${projectId}/adrs${buildQuery({
      status: params?.status,
      search: params?.search,
      sort_by: params?.sort_by,
    })}`),
  createAdr: (projectId: string, data: { title: string; template_id?: string; content?: string }) =>
    request<import("./types").Adr>(`/projects/${projectId}/adrs`, { method: "POST", body: JSON.stringify(data) }),
  getAdr: (projectId: string, adrId: string) =>
    request<import("./types").Adr>(`/projects/${projectId}/adrs/${adrId}`),
  updateAdr: (projectId: string, adrId: string, data: { title?: string; content?: string; status?: string }) =>
    request<import("./types").Adr>(`/projects/${projectId}/adrs/${adrId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAdr: (projectId: string, adrId: string) =>
    request<void>(`/projects/${projectId}/adrs/${adrId}`, { method: "DELETE" }),
  commitAdr: (projectId: string, adrId: string) =>
    request<{ branch: string; sha: string }>(`/projects/${projectId}/adrs/${adrId}/commit`, { method: "POST" }),
  createAdrPr: (projectId: string, adrId: string) =>
    request<{ pr_url: string }>(`/projects/${projectId}/adrs/${adrId}/pr`, { method: "POST" }),
  mergeAdrPr: (projectId: string, adrId: string) =>
    request<{ merged: boolean }>(`/projects/${projectId}/adrs/${adrId}/merge`, { method: "POST" }),
  supersedeAdr: (projectId: string, adrId: string, newAdrId: string) =>
    request<import("./types").Adr>(`/projects/${projectId}/adrs/${adrId}/supersede?new_adr_id=${newAdrId}`, { method: "POST" }),
  generateAdr: (projectId: string, data: { text: string; template_id?: string }) =>
    request<import("./types").Adr>(`/projects/${projectId}/adrs/generate`, { method: "POST", body: JSON.stringify(data) }),

  // Project Schedules
  getProjectSchedule: (projectId: string) =>
    request<import("./types").ProjectSchedule>(`/projects/${projectId}/schedules`),
  updateProjectSchedule: (projectId: string, data: Record<string, string>) =>
    request<import("./types").ProjectSchedule>(`/projects/${projectId}/schedules`, { method: "PUT", body: JSON.stringify(data) }),

  // Presentations
  listPresentations: (projectId: string) =>
    request<import("./types").PresentationListItem[]>(`/projects/${projectId}/presentations`),
  createPresentation: (projectId: string, data: { title: string; description?: string; component_code?: string; prompt?: string; chat_session_id?: string; status?: string }) =>
    request<import("./types").PresentationDetail>(`/projects/${projectId}/presentations`, { method: "POST", body: JSON.stringify(data) }),
  getPresentation: (projectId: string, presId: string) =>
    request<import("./types").PresentationDetail>(`/projects/${projectId}/presentations/${presId}`),
  updatePresentation: (projectId: string, presId: string, data: { title?: string; description?: string; component_code?: string; template_version?: number; status?: string }) =>
    request<import("./types").PresentationDetail>(`/projects/${projectId}/presentations/${presId}`, { method: "PATCH", body: JSON.stringify(data) }),
  deletePresentation: (projectId: string, presId: string) =>
    request<void>(`/projects/${projectId}/presentations/${presId}`, { method: "DELETE" }),
  listPresentationVersions: (projectId: string, presId: string) =>
    request<import("./types").PresentationVersion[]>(`/projects/${projectId}/presentations/${presId}/versions`),
  getPresentationTemplate: (version: number) =>
    request<import("./types").PresentationTemplate>(`/presentations/templates/${version}`),
  getLatestPresentationTemplate: () =>
    request<import("./types").PresentationTemplate>(`/presentations/templates/latest`),
  executePresentationQuery: (projectId: string, toolSlug: string, params: Record<string, unknown>) =>
    request<{ result: unknown }>(`/projects/${projectId}/presentations/data`, { method: "POST", body: JSON.stringify({ tool_slug: toolSlug, params }) }),

  // Access policies (admin / RBAC)
  listAccessPolicies: (params?: { scope_type?: string }) =>
    request<AccessPolicy[]>(`/access-policies${buildQuery({ scope_type: params?.scope_type })}`),
  createAccessPolicy: (data: AccessPolicyCreate) =>
    request<AccessPolicy>("/access-policies", { method: "POST", body: JSON.stringify(data) }),
  updateAccessPolicy: (id: string, data: AccessPolicyUpdate) =>
    request<AccessPolicy>(`/access-policies/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAccessPolicy: (id: string) =>
    request<void>(`/access-policies/${id}`, { method: "DELETE" }),

  // Code Reviews
  listCodeReviews: (projectId: string, params?: {
    status?: string; trigger?: string; verdict?: string;
    repository_id?: string; limit?: number; offset?: number;
  }) => request<import("./types").CodeReviewRunItem[]>(
    `/projects/${projectId}/code-reviews${buildQuery({
      status: params?.status,
      trigger: params?.trigger,
      verdict: params?.verdict,
      repository_id: params?.repository_id,
      limit: params?.limit?.toString(),
      offset: params?.offset?.toString(),
    })}`
  ),
  getCodeReview: (projectId: string, runId: string) =>
    request<import("./types").CodeReviewRunItem>(`/projects/${projectId}/code-reviews/${runId}`),
  getCodeReviewSummary: (projectId: string) =>
    request<import("./types").CodeReviewSummary>(`/projects/${projectId}/code-reviews/summary`),
  triggerCodeReview: (projectId: string, repositoryId: string, prNumber: number) =>
    request<{ status: string; review_run_id: string; celery_task_id: string }>(
      `/webhooks/projects/${projectId}/code-reviews`,
      { method: "POST", body: JSON.stringify({ repository_id: repositoryId, pr_number: prNumber }) },
    ),

  getApiBase: () => API_BASE,
  getSseBase: () => API_BASE,
  getAuthToken: () => getToken(),
};
