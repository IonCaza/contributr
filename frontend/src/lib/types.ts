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
  platform_credential_id: string | null;
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
  avg_commit_size: number;
  code_velocity: number;
  merge_ratio: number;
  active_days: number;
  review_engagement: number;
  impact_score: number;
  prs_authored: number;
  reviews_given: number;
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

export interface DeliverySummary {
  active_contributors_30d: number;
  total_contributors: number;
  open_prs: number;
  merged_prs_7d: number;
  merged_prs_wow_delta: number;
  pr_cycle_time_hours: number;
  review_turnaround_hours: number;
  total_work_items: number;
  open_work_items: number;
  completed_work_items_30d: number;
  wi_cycle_time_hours: number;
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
  churn_ratio: number;
  pr_cycle_time_hours: number;
  pr_review_turnaround_hours: number;
  contribution_gini: number;
  trends: TrendData;
}

export interface RepoStats {
  total_commits: number;
  contributor_count: number;
  bus_factor: number;
  churn_ratio: number;
  pr_cycle_time_hours: number;
  pr_review_turnaround_hours: number;
  contribution_gini: number;
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

export interface AiSettings {
  enabled: boolean;
}

export interface AiStatus {
  enabled: boolean;
  configured: boolean;
}

export interface LlmProvider {
  id: string;
  name: string;
  provider_type: string;
  model: string;
  has_api_key: boolean;
  base_url: string | null;
  temperature: number;
  context_window: number | null;
  is_default: boolean;
}

export interface AgentConfig {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  llm_provider_id: string | null;
  system_prompt: string;
  max_iterations: number;
  summary_token_limit: number | null;
  enabled: boolean;
  is_builtin: boolean;
  tool_slugs: string[];
  knowledge_graph_ids: string[];
}

export interface KnowledgeGraphListItem {
  id: string;
  name: string;
  description: string | null;
  generation_mode: string;
  excluded_entities: string[];
  node_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeGraph {
  id: string;
  name: string;
  description: string | null;
  generation_mode: string;
  content: string;
  graph_data: {
    nodes: KGNode[];
    edges: KGEdge[];
  };
  excluded_entities: string[];
  created_at: string;
  updated_at: string;
}

export interface KGNode {
  id: string;
  label: string;
  description?: string;
  columns?: { name: string; type: string; pk?: boolean; unique?: boolean; required?: boolean; comment?: string }[];
  row_count?: number;
}

export interface KGEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  type: "fk" | "m2m";
}

export interface ToolDefinition {
  slug: string;
  name: string;
  description: string;
  category: string;
}

export interface ChatSession {
  id: string;
  title: string;
  agent_slug: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  created_at: string;
}

export interface CommitFileItem {
  id: string;
  file_path: string;
  lines_added: number;
  lines_deleted: number;
}

export interface CommitDetail extends CommitItem {
  files: CommitFileItem[];
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  commits: number;
  contributors: number;
  lines_added: number;
  lines_deleted: number;
  last_modified: string | null;
  children?: FileTreeNode[];
}

export interface FileDetail {
  path: string;
  total_commits: number;
  total_lines_added: number;
  total_lines_deleted: number;
  primary_owner: { id: string; name: string; email: string; commits: number } | null;
  contributors: { id: string; name: string; email: string; commits: number; lines_added: number; lines_deleted: number; last_touched: string }[];
  recent_commits: CommitItem[];
}

export interface HotspotFile {
  file_path: string;
  commit_count: number;
  contributor_count: number;
  total_lines_added: number;
  total_lines_deleted: number;
  bus_factor: number;
}

export interface PRStatItem {
  id: string;
  title: string | null;
  state: string;
  repository_id: string;
  contributor_id: string | null;
  created_at: string;
  merged_at: string | null;
  cycle_time_hours: number | null;
  review_turnaround_hours: number | null;
}

export interface FileExclusionPattern {
  id: string;
  pattern: string;
  description: string | null;
  enabled: boolean;
  is_default: boolean;
  created_at: string | null;
}

export interface PlatformCredential {
  id: string;
  name: string;
  platform: string;
  base_url: string | null;
  created_at: string;
}

export interface PlatformCredentialTestResult {
  success: boolean;
  message: string;
}

// ── Delivery / Teams ────────────────────────────────────────────────

export interface Team {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  platform: string | null;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  contributor_id: string;
  contributor_name: string;
  contributor_email: string;
  role: string;
  joined_at: string;
}

export interface Iteration {
  id: string;
  name: string;
  path: string | null;
  start_date: string | null;
  end_date: string | null;
  stats: IterationStats | null;
}

export interface IterationStats {
  total_items: number;
  completed_items: number;
  total_points: number;
  completed_points: number;
}

export interface WorkItem {
  id: string;
  platform_work_item_id: number;
  work_item_type: "epic" | "feature" | "user_story" | "task" | "bug";
  title: string;
  state: string;
  description?: string | null;
  assigned_to: { id: string; name: string | null } | null;
  iteration_id: string | null;
  iteration_name: string | null;
  story_points: number | null;
  priority: number | null;
  tags: string[];
  created_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  platform_url: string | null;
  children_count: number;
  parent_id: string | null;
}

export interface PaginatedWorkItems {
  items: WorkItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkItemTreeNode {
  id: string;
  platform_work_item_id: number;
  work_item_type: "epic" | "feature" | "user_story" | "task" | "bug";
  title: string;
  state: string;
  assigned_to: { id: string; name: string | null } | null;
  iteration_id: string | null;
  iteration_name: string | null;
  story_points: number | null;
  priority: number | null;
  tags: string[];
  created_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  platform_url: string | null;
  children: WorkItemTreeNode[];
}

export interface WorkItemsTreeResponse {
  roots: WorkItemTreeNode[];
  total_count: number;
}

export interface DeliveryStats {
  total_work_items: number;
  open_items: number;
  completed_items: number;
  total_story_points: number;
  completed_story_points: number;
  avg_cycle_time_hours: number;
  avg_lead_time_hours: number;
  velocity_trend: { iteration: string; points: number }[];
  throughput_trend: { date: string; completed: number; created: number }[];
  cycle_time_trend?: { week: string; median_hours: number }[];
  lead_time_trend?: { week: string; median_hours: number }[];
  backlog_by_type: { type: string; count: number }[];
  backlog_by_state: { state: string; count: number }[];
}

export interface DeliveryFilters {
  iteration_ids?: string[];
  from_date?: string;
  to_date?: string;
  team_id?: string;
  contributor_id?: string;
}

export interface FlowMetrics {
  cycle_time_distribution: { range: string; count: number }[];
  wip_by_state: { state: string; count: number }[];
  cumulative_flow: {
    states: string[];
    data: Record<string, string | number>[];
  };
}

export interface BacklogHealthMetrics {
  stale_items: { type: string; count: number }[];
  age_distribution: { range: string; count: number }[];
  growth: { date: string; created: number; completed: number; net: number }[];
}

export interface QualityMetrics {
  bug_trend: { date: string; created: number; resolved: number }[];
  resolution_time: { median_hours: number; p90_hours: number; sample_size: number };
  defect_density: { bugs: number; total: number; ratio: number };
}

export interface IntersectionMetrics {
  total_linked_items: number;
  total_items: number;
  link_coverage_pct: number;
  commits_per_story_point: number;
  avg_first_commit_to_resolution_hours: number;
}

export interface BurndownPoint {
  date: string;
  remaining: number;
  ideal: number;
}

export interface SprintDetail extends Iteration {
  burndown: BurndownPoint[];
  work_items: WorkItem[];
  contributors: { id: string; name: string | null; total: number; completed: number }[];
}

export interface TeamDetail {
  id: string;
  name: string;
  description: string | null;
  platform: string | null;
  members: { id: string; name: string | null; email: string | null; role: string }[];
  work_item_summary: { state: string; count: number }[];
}

// ── Team Analytics ──────────────────────────────────────────────────

export interface TeamCodeStats {
  total_commits: number;
  lines_added: number;
  lines_deleted: number;
  files_changed: number;
  prs_opened: number;
  prs_merged: number;
  reviews_given: number;
  active_repos: number;
  avg_commit_size: number;
}

export interface TeamCodeActivity {
  date: string;
  commits: number;
  lines_added: number;
  lines_deleted: number;
}

export interface TeamMemberCodeStats {
  id: string;
  name: string;
  commits: number;
  lines_added: number;
  lines_deleted: number;
  prs_opened: number;
  prs_merged: number;
  reviews_given: number;
}

export interface WorkItemDetail extends WorkItem {
  description: string | null;
  custom_fields: Record<string, unknown> | null;
  original_estimate: number | null;
  remaining_work: number | null;
  completed_work: number | null;
  created_by: { id: string; name: string | null } | null;
  iteration: { id: string; name: string | null } | null;
  area_path: string | null;
  state_changed_at: string | null;
  activated_at: string | null;
  updated_at: string;
  parent: { id: string; title: string; work_item_type: string } | null;
  children: { id: string; title: string; work_item_type: string; state: string; story_points: number | null }[];
  linked_commits: LinkedCommit[];
}

export interface WorkItemDetailRow {
  id: string;
  platform_work_item_id: number;
  title: string;
  work_item_type: string;
  state: string;
  story_points: number | null;
  priority: number | null;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  iteration_name: string | null;
  created_at: string | null;
  activated_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  updated_at: string | null;
  platform_url: string | null;
  cycle_time_hours: number | null;
  lead_time_hours: number | null;
  linked_commit_count: number;
  first_commit_to_resolution_hours: number | null;
}

export interface ContributorDeliverySummary {
  contributor_id: string;
  contributor_name: string | null;
  total_items: number;
  completed_items: number;
  open_items: number;
  total_sp: number;
  completed_sp: number;
  avg_cycle_time_hours: number | null;
}

export interface LinkedCommit {
  id: string;
  sha: string;
  message: string | null;
  authored_at: string;
  link_type: string;
  contributor: { id: string; name: string | null } | null;
}

// Custom field import configuration
export interface CustomFieldConfig {
  id: string;
  project_id: string;
  field_reference_name: string;
  display_name: string;
  field_type: string;
  enabled: boolean;
}

export interface DiscoveredField {
  reference_name: string;
  name: string;
  field_type: string;
  is_configured: boolean;
}

// ── Insights ────────────────────────────────────────────────────────

export interface InsightRun {
  id: string;
  project_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  findings_count: number;
  error_message: string | null;
}

export interface InsightFinding {
  id: string;
  run_id: string;
  project_id: string;
  category: string;
  severity: string;
  slug: string;
  title: string;
  description: string;
  recommendation: string;
  metric_data: Record<string, unknown> | null;
  affected_entities: Record<string, unknown> | null;
  status: string;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
  dismissed_at: string | null;
  dismissed_by_id: string | null;
}

export interface InsightsSummary {
  total_active: number;
  critical: number;
  warning: number;
  info: number;
  resolved_30d: number;
  by_category: Record<string, number>;
}

// ── Contributor Insights ────────────────────────────────────────────

export interface ContributorInsightRun {
  id: string;
  contributor_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  findings_count: number;
  error_message: string | null;
}

export interface ContributorInsightFinding {
  id: string;
  run_id: string;
  contributor_id: string;
  category: string;
  severity: string;
  slug: string;
  title: string;
  description: string;
  recommendation: string;
  metric_data: Record<string, unknown> | null;
  affected_entities: Record<string, unknown> | null;
  status: string;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
  dismissed_at: string | null;
  dismissed_by_id: string | null;
}

export interface ContributorInsightsSummary {
  total_active: number;
  critical: number;
  warning: number;
  info: number;
  resolved_30d: number;
  by_category: Record<string, number>;
}

// ── Team Insights ───────────────────────────────────────────────────

export interface TeamInsightRun {
  id: string;
  team_id: string;
  project_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  findings_count: number;
  error_message: string | null;
}

export interface TeamInsightFinding {
  id: string;
  run_id: string;
  team_id: string;
  project_id: string;
  category: string;
  severity: string;
  slug: string;
  title: string;
  description: string;
  recommendation: string;
  metric_data: Record<string, unknown> | null;
  affected_entities: Record<string, unknown> | null;
  status: string;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
  dismissed_at: string | null;
  dismissed_by_id: string | null;
}

export interface TeamInsightsSummary {
  total_active: number;
  critical: number;
  warning: number;
  info: number;
  resolved_30d: number;
  by_category: Record<string, number>;
}
