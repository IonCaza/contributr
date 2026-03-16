"use client";

import { use, useState, useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  GitPullRequest, MessageSquare, Clock, ArrowUpDown, Search,
  ChevronLeft, ChevronRight, BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
            <>
              {/* Size Distribution */}
              <div>
                <h3 className="text-sm font-semibold mb-3">PR Size Distribution</h3>
                <div className="grid grid-cols-5 gap-3">
                  {analytics.size_distribution.map((b) => (
                    <Card key={b.label} className="p-4 text-center">
                      <div className="text-2xl font-bold">{b.count}</div>
                      <div className="text-xs text-muted-foreground">{b.label}</div>
                      {b.avg_cycle_time_hours !== null && (
                        <div className="text-[10px] text-muted-foreground mt-1">
                          avg {formatCycleTime(b.avg_cycle_time_hours)}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              </div>

              {/* Cycle Time Trend */}
              {analytics.cycle_time_trend.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-3">Cycle Time Trend (weekly)</h3>
                  <Card className="p-4">
                    <div className="flex items-end gap-1 h-32">
                      {analytics.cycle_time_trend.map((t, i) => {
                        const maxH = Math.max(...analytics.cycle_time_trend.map((x) => x.avg_cycle_time_hours || 0));
                        const pct = maxH > 0 ? ((t.avg_cycle_time_hours || 0) / maxH) * 100 : 0;
                        return (
                          <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <div
                              className="w-full bg-primary/20 rounded-t"
                              style={{ height: `${Math.max(pct, 2)}%` }}
                              title={`${t.period}: ${formatCycleTime(t.avg_cycle_time_hours)} (${t.pr_count} PRs)`}
                            />
                            {i % Math.ceil(analytics.cycle_time_trend.length / 8) === 0 && (
                              <span className="text-[8px] text-muted-foreground truncate w-full text-center">
                                {t.period.slice(-3)}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                </div>
              )}

              {/* Top Reviewers */}
              {analytics.top_reviewers.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-3">Top Reviewers</h3>
                  <Card>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Reviewer</TableHead>
                          <TableHead>Reviews</TableHead>
                          <TableHead>Approvals</TableHead>
                          <TableHead>Avg Turnaround</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {analytics.top_reviewers.map((r, i) => (
                          <TableRow key={i}>
                            <TableCell className="font-medium">
                              {r.reviewer_id ? (
                                <Link href={`/contributors/${r.reviewer_id}`} className="hover:underline">{r.reviewer_name}</Link>
                              ) : (
                                r.reviewer_name
                              )}
                            </TableCell>
                            <TableCell>{r.review_count}</TableCell>
                            <TableCell>{r.approval_count}</TableCell>
                            <TableCell>{formatCycleTime(r.avg_turnaround_hours)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Card>
                </div>
              )}

              {/* Summary */}
              <div className="grid grid-cols-4 gap-4">
                <Card className="p-4 text-center">
                  <div className="text-2xl font-bold">{analytics.total_prs}</div>
                  <div className="text-xs text-muted-foreground">Total PRs</div>
                </Card>
                <Card className="p-4 text-center">
                  <div className="text-2xl font-bold">{analytics.merged_prs}</div>
                  <div className="text-xs text-muted-foreground">Merged</div>
                </Card>
                <Card className="p-4 text-center">
                  <div className="text-2xl font-bold">{analytics.closed_prs}</div>
                  <div className="text-xs text-muted-foreground">Closed</div>
                </Card>
                <Card className="p-4 text-center">
                  <div className="text-2xl font-bold">{analytics.open_prs}</div>
                  <div className="text-xs text-muted-foreground">Open</div>
                </Card>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
