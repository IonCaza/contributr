export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  is_admin: boolean;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  repositories: RepoSummary[];
  contributors: ContributorSummary[];
}

export interface RepoSummary {
  id: string;
  name: string;
  ssh_url: string | null;
  clone_url: string | null;
  platform: string;
  platform_owner: string | null;
  platform_repo: string | null;
  default_branch: string;
  ssh_credential_id: string | null;
  last_synced_at: string | null;
}

export interface Repository {
  id: string;
  project_id: string;
  name: string;
  clone_url: string | null;
  ssh_url: string | null;
  platform: string;
  platform_owner: string | null;
  platform_repo: string | null;
  default_branch: string;
  ssh_credential_id: string | null;
  last_synced_at: string | null;
  created_at: string;
}

export interface ContributorSummary {
  id: string;
  canonical_name: string;
  canonical_email: string;
}

export interface ProjectBrief {
  id: string;
  name: string;
}

export interface Contributor extends ContributorSummary {
  alias_emails: string[] | null;
  alias_names: string[] | null;
  github_username: string | null;
  gitlab_username: string | null;
  azure_username: string | null;
  projects: ProjectBrief[];
  created_at: string;
}

export interface DuplicateGroup {
  group_key: string;
  reason: string;
  contributor_ids: string[];
}

export interface ContributorStats {
  total_commits: number;
  total_lines_added: number;
  total_lines_deleted: number;
  repository_count: number;
  current_streak_days: number;
  trends: TrendData;
}

export interface TrendData {
  avg_commits_7d: number;
  avg_commits_30d: number;
  avg_lines_7d: number;
  avg_lines_30d: number;
  wow_commits_delta: number;
  wow_lines_delta: number;
  current_week: { commits: number; lines_added: number; lines_deleted: number };
  previous_week: { commits: number; lines_added: number; lines_deleted: number };
}

export interface DailyStat {
  date: string;
  contributor_id: string;
  repository_id: string;
  commits: number;
  lines_added: number;
  lines_deleted: number;
  files_changed: number;
  merges: number;
  prs_opened: number;
  prs_merged: number;
  reviews_given: number;
}

export interface ProjectStats {
  repository_count: number;
  total_commits: number;
  contributor_count: number;
  trends: TrendData;
}

export interface RepoStats {
  total_commits: number;
  contributor_count: number;
  bus_factor: number;
  trends: TrendData;
}

export interface SSHKey {
  id: string;
  name: string;
  key_type: string;
  public_key: string;
  fingerprint: string;
  created_at: string;
}

export interface SyncJob {
  id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface Branch {
  id: string;
  name: string;
  is_default: boolean;
}

export interface CommitItem {
  id: string;
  sha: string;
  message: string | null;
  authored_at: string;
  lines_added: number;
  lines_deleted: number;
  files_changed: number;
  is_merge: boolean;
  contributor_name: string | null;
  contributor_email: string | null;
  repository_name: string | null;
  repository_id: string;
  commit_url: string | null;
  branches: string[];
}

export interface PaginatedCommits {
  items: CommitItem[];
  total: number;
  page: number;
  per_page: number;
}
