import type {
  TokenResponse, User, Project, ProjectDetail, ProjectStats,
  Repository, RepoStats, Contributor, ContributorStats, DailyStat,
  SSHKey, SyncJob, TrendData, Branch, PaginatedCommits, ContributorSummary,
  DuplicateGroup, CommitDetail, FileTreeNode, FileDetail, HotspotFile, PRStatItem,
  ChatSession, ChatMessage, AiSettings, AiStatus, FileExclusionPattern,
  PlatformCredential, PlatformCredentialTestResult,
  LlmProvider, AgentConfig, ToolDefinition,
  KnowledgeGraphListItem, KnowledgeGraph,
  Team, TeamMember, DeliveryStats, PaginatedWorkItems, Iteration,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

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
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  refresh: (refresh_token: string) =>
    request<TokenResponse>(`/auth/refresh?refresh_token=${refresh_token}`, { method: "POST" }),
  me: () => request<User>("/auth/me"),
  listUsers: () => request<User[]>("/auth/users"),
  createUser: (data: { email: string; username: string; password: string; full_name?: string; is_admin?: boolean }) =>
    request<User>("/auth/users", { method: "POST", body: JSON.stringify(data) }),
  deleteUser: (id: string) => request<void>(`/auth/users/${id}`, { method: "DELETE" }),

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
  updateAiSettings: (data: { enabled?: boolean }) =>
    request<AiSettings>("/ai/settings", { method: "PUT", body: JSON.stringify(data) }),
  getAiStatus: () => request<AiStatus>("/ai/settings/status"),

  // LLM Providers
  listLlmProviders: () => request<LlmProvider[]>("/ai/llm-providers"),
  createLlmProvider: (data: { name: string; provider_type?: string; model: string; api_key?: string; base_url?: string; temperature?: number; context_window?: number | null; is_default?: boolean }) =>
    request<LlmProvider>("/ai/llm-providers", { method: "POST", body: JSON.stringify(data) }),
  updateLlmProvider: (id: string, data: { name?: string; provider_type?: string; model?: string; api_key?: string; base_url?: string; temperature?: number; context_window?: number | null; is_default?: boolean }) =>
    request<LlmProvider>(`/ai/llm-providers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteLlmProvider: (id: string) => request<void>(`/ai/llm-providers/${id}`, { method: "DELETE" }),

  // Agents
  listAgents: () => request<AgentConfig[]>("/ai/agents"),
  getAgent: (slug: string) => request<AgentConfig>(`/ai/agents/${slug}`),
  createAgent: (data: { slug: string; name: string; description?: string; llm_provider_id?: string; system_prompt?: string; max_iterations?: number; summary_token_limit?: number | null; enabled?: boolean; tool_slugs?: string[]; knowledge_graph_ids?: string[] }) =>
    request<AgentConfig>("/ai/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (slug: string, data: { name?: string; description?: string; llm_provider_id?: string; system_prompt?: string; max_iterations?: number; summary_token_limit?: number | null; enabled?: boolean; tool_slugs?: string[]; knowledge_graph_ids?: string[] }) =>
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
  getDeliveryStats: (projectId: string, params?: { team_id?: string; contributor_id?: string }) =>
    request<DeliveryStats>(`/projects/${projectId}/delivery/stats${buildQuery({ team_id: params?.team_id, contributor_id: params?.contributor_id })}`),
  listWorkItems: (projectId: string, params?: { work_item_type?: string; state?: string; assignee_id?: string; iteration_id?: string; parent_id?: string; page?: number; page_size?: number }) =>
    request<PaginatedWorkItems>(`/projects/${projectId}/delivery/work-items${buildQuery({
      work_item_type: params?.work_item_type,
      state: params?.state,
      assignee_id: params?.assignee_id,
      iteration_id: params?.iteration_id,
      parent_id: params?.parent_id,
      page: params?.page?.toString(),
      page_size: params?.page_size?.toString(),
    })}`),
  getWorkItem: (projectId: string, workItemId: string) =>
    request<unknown>(`/projects/${projectId}/delivery/work-items/${workItemId}`),
  listIterations: (projectId: string) =>
    request<Iteration[]>(`/projects/${projectId}/delivery/iterations`),
  getIteration: (projectId: string, iterationId: string) =>
    request<Iteration>(`/projects/${projectId}/delivery/iterations/${iterationId}`),
  getVelocity: (projectId: string, limit?: number) =>
    request<{ iteration: string; points: number }[]>(`/projects/${projectId}/delivery/velocity${buildQuery({ limit: limit?.toString() })}`),
  getDeliveryTrends: (projectId: string, days?: number) =>
    request<{ date: string; created: number; completed: number }[]>(`/projects/${projectId}/delivery/trends${buildQuery({ days: days?.toString() })}`),
  triggerDeliverySync: (projectId: string) =>
    request<{ task_id: string; job_id: string; status: string }>(`/projects/${projectId}/delivery/sync`, { method: "POST" }),
  listDeliverySyncJobs: (projectId: string) =>
    request<{ id: string; status: string; started_at: string | null; finished_at: string | null; error_message: string | null; created_at: string }[]>(`/projects/${projectId}/delivery/sync-jobs`),
  getDeliverySyncLogUrl: (projectId: string) =>
    `${API_BASE}/projects/${projectId}/delivery/sync/logs`,

  getApiBase: () => API_BASE,
  getAuthToken: () => getToken(),
};
