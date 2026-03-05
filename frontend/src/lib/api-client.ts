import type {
  TokenResponse, User, Project, ProjectDetail, ProjectStats,
  Repository, RepoStats, Contributor, ContributorStats, DailyStat,
  SSHKey, SyncJob, TrendData, Branch, PaginatedCommits, ContributorSummary,
  DuplicateGroup,
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
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
  updateProject: (id: string, data: { name?: string; description?: string }) =>
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
  syncRepo: (id: string) => request<SyncJob>(`/repositories/${id}/sync`, { method: "POST" }),
  cancelSyncJob: (repoId: string, jobId: string) =>
    request<SyncJob>(`/repositories/${repoId}/sync-jobs/${jobId}/cancel`, { method: "POST" }),
  getRepoStats: (id: string, branches?: string[]) =>
    request<RepoStats>(`/repositories/${id}/stats${buildQuery({ branch: branches })}`),
  listSyncJobs: (id: string) => request<SyncJob[]>(`/repositories/${id}/sync-jobs`),
  listBranches: (repoId: string, contributorId?: string) =>
    request<Branch[]>(`/repositories/${repoId}/branches${buildQuery({ contributor_id: contributorId })}`),
  listRepoContributors: (repoId: string, branches?: string[]) =>
    request<ContributorSummary[]>(`/repositories/${repoId}/contributors${buildQuery({ branch: branches })}`),
  listRepoCommits: (repoId: string, params?: { branch?: string[]; contributor_id?: string; page?: number; per_page?: number }) =>
    request<PaginatedCommits>(`/commits/by-repo/${repoId}${buildQuery({
      branch: params?.branch,
      contributor_id: params?.contributor_id,
      page: params?.page?.toString(),
      per_page: params?.per_page?.toString(),
    })}`),
  listContributorCommits: (contributorId: string, params?: { repository_id?: string; branch?: string[]; from_date?: string; to_date?: string; page?: number; per_page?: number }) =>
    request<PaginatedCommits>(`/commits/by-contributor/${contributorId}${buildQuery({
      repository_id: params?.repository_id,
      branch: params?.branch,
      from_date: params?.from_date,
      to_date: params?.to_date,
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

  // SSH Keys
  listSSHKeys: () => request<SSHKey[]>("/ssh-keys"),
  createSSHKey: (data: { name: string; key_type: string; rsa_bits?: number }) =>
    request<SSHKey>("/ssh-keys", { method: "POST", body: JSON.stringify(data) }),
  deleteSSHKey: (id: string) => request<void>(`/ssh-keys/${id}`, { method: "DELETE" }),

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
};
