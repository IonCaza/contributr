import type { DateRange } from "@/components/date-range-filter";

export const queryKeys = {
  projects: {
    all: ["projects"] as const,
    detail: (id: string) => ["projects", id] as const,
    stats: (id: string, range?: { from?: string; to?: string }) => ["projects", id, "stats", range] as const,
    prStats: (id: string) => ["projects", id, "prStats"] as const,
  },
  repos: {
    list: (projectId: string) => ["projects", projectId, "repos"] as const,
    detail: (id: string) => ["repos", id] as const,
    stats: (id: string, filters?: { branches?: string[]; from?: string; to?: string }) => ["repos", id, "stats", filters] as const,
    syncJobs: (id: string) => ["repos", id, "syncJobs"] as const,
    branches: (id: string, contributorId?: string) => ["repos", id, "branches", contributorId] as const,
    contributors: (id: string, branches?: string[]) => ["repos", id, "contributors", branches] as const,
    fileTree: (id: string, branch?: string) => ["repos", id, "fileTree", branch] as const,
    hotspots: (id: string, branch?: string) => ["repos", id, "hotspots", branch] as const,
    fileDetail: (id: string, path: string, branch?: string) => ["repos", id, "files", path, branch] as const,
    commits: (id: string, filters?: Record<string, unknown>) => ["repos", id, "commits", filters] as const,
  },
  contributors: {
    all: (projectId?: string) => ["contributors", { projectId }] as const,
    duplicates: ["contributors", "duplicates"] as const,
    detail: (id: string) => ["contributors", id] as const,
    stats: (id: string, filters?: Record<string, unknown>) => ["contributors", id, "stats", filters] as const,
    repos: (id: string) => ["contributors", id, "repos"] as const,
    commits: (id: string, filters?: Record<string, unknown>) => ["contributors", id, "commits", filters] as const,
  },
  daily: (params: Record<string, unknown>) => ["dailyStats", params] as const,
  trends: (params: Record<string, unknown>) => ["trends", params] as const,
  deliverySummary: ["deliverySummary"] as const,
  sshKeys: ["sshKeys"] as const,
  platformCredentials: ["platformCredentials"] as const,
  users: ["users"] as const,
  fileExclusions: ["fileExclusions"] as const,
  aiSettings: ["aiSettings"] as const,
  aiStatus: ["aiStatus"] as const,
  llmProviders: ["llmProviders"] as const,
  agents: ["agents"] as const,
  agentDetail: (slug: string) => ["agents", slug] as const,
  aiTools: ["aiTools"] as const,
  knowledgeGraphs: ["knowledgeGraphs"] as const,
  knowledgeGraphDetail: (id: string) => ["knowledgeGraphs", id] as const,
  commitDetail: (id: string) => ["commitDetail", id] as const,
  teams: {
    all: (projectId?: string) => ["teams", { projectId }] as const,
    detail: (id: string) => ["teams", id] as const,
    members: (id: string) => ["teams", id, "members"] as const,
  },
  delivery: {
    stats: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "stats", filters] as const,
    workItems: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "workItems", filters] as const,
    workItemsTree: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "workItemsTree", filters] as const,
    iterations: (projectId: string) => ["delivery", projectId, "iterations"] as const,
    velocity: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "velocity", filters] as const,
    trends: (projectId: string) => ["delivery", projectId, "trends"] as const,
    syncJobs: (projectId: string) => ["delivery", projectId, "syncJobs"] as const,
    flow: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "flow", filters] as const,
    backlogHealth: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "backlogHealth", filters] as const,
    quality: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "quality", filters] as const,
    intersection: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "intersection", filters] as const,
    workItemDetail: (projectId: string, workItemId: string) => ["delivery", projectId, "workItem", workItemId] as const,
    workItemCommits: (projectId: string, workItemId: string) => ["delivery", projectId, "workItem", workItemId, "commits"] as const,
    sprintDetail: (projectId: string, iterationId: string) => ["delivery", projectId, "sprint", iterationId] as const,
    sprintBurndown: (projectId: string, iterationId: string) => ["delivery", projectId, "sprint", iterationId, "burndown"] as const,
    teamDetail: (projectId: string, teamId: string) => ["delivery", projectId, "team", teamId] as const,
    teams: (projectId: string) => ["delivery", projectId, "teams"] as const,
    itemDetails: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "itemDetails", filters] as const,
    contributorSummary: (projectId: string, filters?: Record<string, unknown>) => ["delivery", projectId, "contributorSummary", filters] as const,
    workItemActivities: (projectId: string, workItemId: string, params?: Record<string, unknown>) => ["delivery", projectId, "workItem", workItemId, "activities", params] as const,
    contributorActivities: (projectId: string, contributorId: string, params?: Record<string, unknown>) => ["delivery", projectId, "contributorActivities", contributorId, params] as const,
    contributorActivityMetrics: (projectId: string, contributorId: string, params?: Record<string, unknown>) => ["delivery", projectId, "contributorActivityMetrics", contributorId, params] as const,
  },
  insights: {
    findings: (projectId: string, filters?: Record<string, unknown>) => ["insights", projectId, "findings", filters] as const,
    summary: (projectId: string) => ["insights", projectId, "summary"] as const,
    runs: (projectId: string) => ["insights", projectId, "runs"] as const,
  },
  teamAnalytics: {
    codeStats: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "code", range] as const,
    codeActivity: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "codeActivity", range] as const,
    memberStats: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "members", range] as const,
    deliveryStats: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "delivery", range] as const,
    deliveryVelocity: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "velocity", range] as const,
    deliveryFlow: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "flow", range] as const,
    deliveryBacklog: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "backlog", range] as const,
    deliveryQuality: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "quality", range] as const,
    deliveryIntersection: (projectId: string, teamId: string, range?: DateRange) =>
      ["teamAnalytics", projectId, teamId, "intersection", range] as const,
    workItems: (projectId: string, teamId: string, filters?: Record<string, unknown>) =>
      ["teamAnalytics", projectId, teamId, "workItems", filters] as const,
    insights: (projectId: string, teamId: string) =>
      ["teamAnalytics", projectId, teamId, "insights"] as const,
  },
  contributorInsights: {
    findings: (contributorId: string, filters?: Record<string, unknown>) => ["contributorInsights", contributorId, "findings", filters] as const,
    summary: (contributorId: string) => ["contributorInsights", contributorId, "summary"] as const,
    runs: (contributorId: string) => ["contributorInsights", contributorId, "runs"] as const,
  },
  teamInsights: {
    findings: (projectId: string, teamId: string, filters?: Record<string, unknown>) => ["teamInsights", projectId, teamId, "findings", filters] as const,
    summary: (projectId: string, teamId: string) => ["teamInsights", projectId, teamId, "summary"] as const,
    runs: (projectId: string, teamId: string) => ["teamInsights", projectId, teamId, "runs"] as const,
  },
  dependencies: {
    findings: (id: string, scope: "repo" | "project", filters?: Record<string, unknown>) => ["dependencies", scope, id, "findings", filters] as const,
    summary: (id: string, scope: "repo" | "project") => ["dependencies", scope, id, "summary"] as const,
    runs: (id: string, scope: "repo" | "project") => ["dependencies", scope, id, "runs"] as const,
    settings: ["dependencies", "settings"] as const,
  },
  sast: {
    findings: (id: string, scope: "repo" | "project", filters?: Record<string, unknown>) => ["sast", scope, id, "findings", filters] as const,
    summary: (id: string, scope: "repo" | "project") => ["sast", scope, id, "summary"] as const,
    runs: (id: string, scope: "repo" | "project") => ["sast", scope, id, "runs"] as const,
    profiles: ["sast", "profiles"] as const,
    settings: ["sast", "settings"] as const,
    ignoredRules: (scope: "global" | string) => ["sast", "ignoredRules", scope] as const,
  },
  feedback: {
    all: (filters?: Record<string, unknown>) => ["feedback", filters] as const,
    detail: (id: string) => ["feedback", id] as const,
  },
  smtpSettings: ["smtpSettings"] as const,
  emailTemplates: ["emailTemplates"] as const,
  emailTemplateDetail: (slug: string) => ["emailTemplates", slug] as const,
  authSettings: ["authSettings"] as const,
  oidcProviders: ["oidcProviders"] as const,
  oidcProviderDetail: (id: string) => ["oidcProviders", id] as const,
  authProviders: ["authProviders"] as const,
};
