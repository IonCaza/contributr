"use client";

import { use, useState, useMemo, useId } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer, AreaChart, Area, BarChart as ReBarChart, Bar,
  CartesianGrid, XAxis, YAxis, Tooltip as ReTooltip, Cell,
} from "recharts";
import {
  GitPullRequest, MessageSquare, Clock, ArrowUpDown, Search,
  ChevronLeft, ChevronRight, BarChart3,
  GitMerge, XCircle, TrendingUp, Users,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatCard } from "@/components/stat-card";
import { FilterBarSkeleton, StatRowSkeleton, TableSkeleton } from "@/components/page-skeleton";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useProject } from "@/hooks/use-projects";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";
import type { PRListItem, PRAnalytics } from "@/lib/types";
import { CodeSubTabs } from "@/components/code-sub-tabs";

const STATE_OPTIONS = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "merged", label: "Merged" },
  { value: "closed", label: "Closed" },
];

function stateColor(state: string) {
  switch (state) {
    case "open": return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "merged": return "bg-purple-500/15 text-purple-700 dark:text-purple-400";
    case "closed": return "bg-red-500/15 text-red-700 dark:text-red-400";
    default: return "bg-muted text-muted-foreground";
  }
}

function formatCycleTime(hours: number | null) {
  if (hours === null || hours === undefined) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

const SIZE_COLORS = [
  { bar: "#34d399" },
  { bar: "#38bdf8" },
  { bar: "#fbbf24" },
  { bar: "#fb923c" },
  { bar: "#fb7185" },
];

const RECHARTS_TOOLTIP_STYLE = {
  backgroundColor: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: "8px",
  color: "var(--popover-foreground)",
  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
  fontSize: 12,
};

function AnalyticsPanel({ analytics, projectId }: { analytics: PRAnalytics; projectId: string }) {
  const gradientId = useId();

  return (
    <div className="space-y-6">
      {/* ── Summary strip ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className={ANIM_CARD} style={stagger(0)}>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15">
                <GitPullRequest className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold tabular-nums">{analytics.total_prs}</p>
                <p className="text-xs text-muted-foreground">Total PRs</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className={ANIM_CARD} style={stagger(1)}>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-500/15">
                <GitMerge className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold tabular-nums">{analytics.merged_prs}</p>
                <p className="text-xs text-muted-foreground">Merged</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className={ANIM_CARD} style={stagger(2)}>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-500/15">
                <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <p className="text-2xl font-bold tabular-nums">{analytics.closed_prs}</p>
                <p className="text-xs text-muted-foreground">Closed</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className={ANIM_CARD} style={stagger(3)}>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green-500/15">
                <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold tabular-nums">{analytics.open_prs}</p>
                <p className="text-xs text-muted-foreground">Open</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Size Distribution ─────────────────────────────────── */}
      <Card className={ANIM_CARD} style={stagger(4)}>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">PR Size Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <ReBarChart
                data={analytics.size_distribution.map((b, i) => ({
                  label: b.label,
                  count: b.count,
                  fill: SIZE_COLORS[i % SIZE_COLORS.length].bar,
                  avg: b.avg_cycle_time_hours,
                }))}
                margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} width={30} />
                <ReTooltip
                  contentStyle={RECHARTS_TOOLTIP_STYLE}
                  formatter={(value, _name, props) => {
                    const lines: [string, string][] = [[`${value}`, "PRs"]];
                    const avg = (props.payload as { avg: number | null })?.avg;
                    if (avg !== null && avg !== undefined) {
                      lines.push([formatCycleTime(avg), "avg cycle time"]);
                    }
                    return lines;
                  }}
                  labelFormatter={(label) => `Size: ${label}`}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={48}>
                  {analytics.size_distribution.map((b, i) => (
                    <Cell key={b.label} fill={SIZE_COLORS[i % SIZE_COLORS.length].bar} />
                  ))}
                </Bar>
              </ReBarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* ── Cycle Time Trend ─────────────────────────────────── */}
      {analytics.cycle_time_trend.length > 0 && (
        <Card className={ANIM_CARD} style={stagger(5)}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Cycle Time Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={analytics.cycle_time_trend.map((t) => ({
                    ...t,
                    hours: t.avg_cycle_time_hours ?? 0,
                    label: t.period,
                  }))}
                  margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                >
                  <defs>
                    <linearGradient id={`ct-grad-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.5} vertical={false} />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickFormatter={(v: string) => v.slice(-3)}
                    interval={Math.max(0, Math.ceil(analytics.cycle_time_trend.length / 8) - 1)}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickFormatter={(v: number) => formatCycleTime(v)}
                    width={40}
                  />
                  <ReTooltip
                    contentStyle={RECHARTS_TOOLTIP_STYLE}
                    itemStyle={{ color: "var(--popover-foreground)" }}
                    labelStyle={{ color: "var(--muted-foreground)", fontWeight: 600, marginBottom: 4 }}
                    formatter={(value) => [formatCycleTime(value as number), "Avg Cycle Time"]}
                    labelFormatter={(label) => label}
                  />
                  <Area
                    type="monotone"
                    dataKey="hours"
                    stroke="var(--chart-1)"
                    strokeWidth={2.5}
                    fill={`url(#ct-grad-${gradientId})`}
                    dot={false}
                    activeDot={{ r: 5, strokeWidth: 2, fill: "var(--background)" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Top Reviewers ─────────────────────────────────────── */}
      {analytics.top_reviewers.length > 0 && (
        <Card className={ANIM_CARD} style={stagger(6)}>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Top Reviewers</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {(() => {
                const maxReviews = Math.max(...analytics.top_reviewers.map((r) => r.review_count));
                return analytics.top_reviewers.map((r, i) => {
                  const approvalRate = r.review_count > 0
                    ? Math.round((r.approval_count / r.review_count) * 100)
                    : 0;
                  const barPct = maxReviews > 0 ? (r.review_count / maxReviews) * 100 : 0;
                  return (
                    <div key={i} className="group flex items-center gap-3 rounded-lg p-2 -mx-2 transition-colors hover:bg-muted/50">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary ring-2 ring-primary/20">
                        {r.reviewer_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            {r.reviewer_id ? (
                              <Link href={`/contributors/${r.reviewer_id}`} className="text-sm font-semibold truncate hover:underline">
                                {r.reviewer_name}
                              </Link>
                            ) : (
                              <span className="text-sm font-semibold truncate">{r.reviewer_name}</span>
                            )}
                            <Badge variant="secondary" className="text-[10px] shrink-0 bg-green-500/15 text-green-700 dark:text-green-400">
                              <CheckCircle2 className="h-3 w-3 mr-0.5" />{approvalRate}%
                            </Badge>
                          </div>
                          <span className="shrink-0 text-xs text-muted-foreground flex items-center gap-1">
                            <Clock className="h-3 w-3" /> {formatCycleTime(r.avg_turnaround_hours)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-2 flex-1 rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-primary/60 transition-all duration-500"
                              style={{ width: `${barPct}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium tabular-nums w-8 text-right">{r.review_count}</span>
                        </div>
                      </div>
                    </div>
                  );
                });
              })()}
              <p className="text-[11px] text-muted-foreground pt-1">Bar length = number of reviews</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function PullRequestsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const { data: project } = useProject(projectId);
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [stateFilter, setStateFilter] = useState("all");
  const [repoFilter, setRepoFilter] = useState("__all__");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [activeTab, setActiveTab] = useState("list");
  const pageSize = 50;

  const listFilters = useMemo(() => ({
    state: stateFilter !== "all" ? stateFilter : undefined,
    repository_id: repoFilter !== "__all__" ? repoFilter : undefined,
    from_date: dateRange.from,
    to_date: dateRange.to,
    search: search || undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
    page,
    page_size: pageSize,
  }), [stateFilter, repoFilter, dateRange, search, sortBy, sortDir, page]);

  const { data: prList, isLoading: listLoading } = useQuery({
    queryKey: queryKeys.pullRequests.list(projectId, listFilters),
    queryFn: () => api.listPullRequests(projectId, listFilters),
    enabled: !!projectId,
  });

  const analyticsFilters = useMemo(() => ({
    from_date: dateRange.from,
    to_date: dateRange.to,
    repository_id: repoFilter !== "__all__" ? repoFilter : undefined,
  }), [dateRange, repoFilter]);

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: queryKeys.pullRequests.analytics(projectId, analyticsFilters),
    queryFn: () => api.getPRAnalytics(projectId, analyticsFilters),
    enabled: !!projectId,
  });

  useRegisterUIContext("pullRequests", {
    prList,
    analytics,
    filters: listFilters,
  });

  function toggleSort(key: string) {
    if (sortBy === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortDir("desc");
    }
    setPage(1);
  }

  const totalPages = prList ? Math.ceil(prList.total / pageSize) : 0;

  if (!project) {
    return (
      <div className="space-y-6">
        <FilterBarSkeleton />
        <StatRowSkeleton />
        <TableSkeleton rows={8} cols={7} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-1 rounded-md border border-border bg-background p-0.5">
          {STATE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { setStateFilter(opt.value); setPage(1); }}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-sm transition-colors",
                stateFilter === opt.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {project.repositories.length > 1 && (
          <Select value={repoFilter} onValueChange={(v) => { setRepoFilter(v); setPage(1); }}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All Repos" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Repositories</SelectItem>
              {project.repositories.map((r) => (
                <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <DateRangeFilter value={dateRange} onChange={(v) => { setDateRange(v); setPage(1); }} />

        <div className="relative ml-auto w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search PR title..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-9"
          />
        </div>
      </div>

      <CodeSubTabs projectId={projectId} />

      {/* Stat Cards */}
      {analytics && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard className={ANIM_CARD} style={stagger(0)} title="Open PRs" value={analytics.open_prs} />
          <StatCard className={ANIM_CARD} style={stagger(1)} title="Avg Cycle Time" value={formatCycleTime(analytics.avg_cycle_time_hours)} />
          <StatCard className={ANIM_CARD} style={stagger(2)} title="Avg Review Turnaround" value={formatCycleTime(analytics.avg_review_turnaround_hours)} />
          <StatCard className={ANIM_CARD} style={stagger(3)} title="Merge Rate" value={analytics.merge_rate !== null ? `${analytics.merge_rate}%` : "—"} />
        </div>
      )}

      {/* Tabs: List / Analytics */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="list" className="gap-1.5">
            <GitPullRequest className="h-3.5 w-3.5" /> PRs
          </TabsTrigger>
          <TabsTrigger value="analytics" className="gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" /> Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-4 mt-4">
          {listLoading ? (
            <TableSkeleton rows={8} cols={7} />
          ) : prList && prList.items.length > 0 ? (
            <>
              <Card>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[40%]">
                        <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("created_at")}>
                          Title <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead>Repository</TableHead>
                      <TableHead>Author</TableHead>
                      <TableHead>State</TableHead>
                      <TableHead>
                        <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("lines_changed")}>
                          +/- <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead>Reviews</TableHead>
                      <TableHead>
                        <button className="flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort("comment_count")}>
                          <MessageSquare className="h-3 w-3" /> <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead>
                        <Clock className="h-3 w-3 inline" /> Cycle
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {prList.items.map((pr: PRListItem) => (
                      <TableRow key={pr.id}>
                        <TableCell>
                          <Link
                            href={`/projects/${projectId}/code/pull-requests/${pr.id}`}
                            className="font-medium hover:underline"
                          >
                            <span className="text-muted-foreground mr-1.5">#{pr.platform_pr_id}</span>
                            {pr.title || "(no title)"}
                          </Link>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {new Date(pr.created_at).toLocaleDateString()}
                            {pr.merged_at && ` → ${new Date(pr.merged_at).toLocaleDateString()}`}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">{pr.repository_name}</TableCell>
                        <TableCell>
                          {pr.author_name && (
                            <div className="flex items-center gap-1.5">
                              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                                {pr.author_name.charAt(0).toUpperCase()}
                              </div>
                              {pr.contributor_id ? (
                                <Link href={`/contributors/${pr.contributor_id}`} className="text-sm hover:underline">
                                  {pr.author_name}
                                </Link>
                              ) : (
                                <span className="text-sm">{pr.author_name}</span>
                              )}
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className={cn("text-[10px]", stateColor(pr.state))}>
                            {pr.state}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs whitespace-nowrap">
                          <span className="text-emerald-500">+{pr.lines_added.toLocaleString()}</span>
                          {" / "}
                          <span className="text-red-500">-{pr.lines_deleted.toLocaleString()}</span>
                        </TableCell>
                        <TableCell className="text-sm">{pr.review_count}</TableCell>
                        <TableCell className="text-sm">{pr.comment_count}</TableCell>
                        <TableCell className="text-sm tabular-nums">{formatCycleTime(pr.cycle_time_hours)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>

              {totalPages > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, prList.total)} of {prList.total}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm">{page} / {totalPages}</span>
                    <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <GitPullRequest className="h-12 w-12 text-muted-foreground/40 mb-3" />
              <h3 className="text-lg font-medium">No pull requests found</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Sync your repositories to fetch pull request data from your platform.
              </p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6 mt-4">
          {analyticsLoading || !analytics ? (
            <StatRowSkeleton />
          ) : (
            <AnalyticsPanel analytics={analytics} projectId={projectId} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
