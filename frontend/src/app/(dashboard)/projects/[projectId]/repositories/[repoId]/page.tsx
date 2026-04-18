"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useActiveRunTracking } from "@/hooks/use-active-run-tracking";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw, AlertCircle, CheckCircle2, Clock, Loader2, XCircle, Ban, Search,
  ArrowUpDown, ChevronDown, ChevronRight, FileCode2, Flame, GitBranch,
  GitCommitHorizontal, ShieldAlert, ShieldCheck, AlertTriangle, Info, Play,
  EyeOff, ExternalLink, Download, Bug, TrendingDown, Package, ArrowUpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatCard } from "@/components/stat-card";
import { FilterBarSkeleton, StatRowSkeleton, ChartSkeleton, TableSkeleton } from "@/components/page-skeleton";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { StatDetailSheet } from "@/components/stat-detail-sheet";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { AuthorBarChart } from "@/components/charts/author-bar-chart";
import { FileTree } from "@/components/file-tree";
import { FileDetailPanel } from "@/components/file-detail-panel";
import { HotspotTable } from "@/components/hotspot-table";
import { CommitList } from "@/components/commit-list";
import { MiniSparkline } from "@/components/charts/mini-sparkline";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { BranchMultiSelect } from "@/components/branch-multi-select";
import { SyncLogViewer, ViewLogsButton } from "@/components/sync-log-viewer";
import { queryKeys } from "@/lib/query-keys";
import { useRepo, useRepoStats, useSyncJobs, useRepoBranches, useRepoContributors, useFileTree, useRepoCommits, useSyncRepo, useCancelSync } from "@/hooks/use-repos";
import { useSastSummary, useSastFindings, useSastRuns } from "@/hooks/use-sast";
import { useDepSummary, useDepFindings, useDepRuns } from "@/hooks/use-dependencies";
import { useDailyStats } from "@/hooks/use-daily-stats";
import { useIterations } from "@/hooks/use-delivery";
import { api } from "@/lib/api-client";
import type { ContributorSummary, SastFinding, SastSummary as SastSummaryType, DepFinding, DepSummary as DepSummaryType } from "@/lib/types";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  failed: <AlertCircle className="h-4 w-4 text-destructive" />,
  running: <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />,
  queued: <Clock className="h-4 w-4 text-muted-foreground" />,
  cancelled: <Ban className="h-4 w-4 text-amber-500" />,
};

const SCAN_STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  failed: <AlertCircle className="h-4 w-4 text-destructive" />,
  running: <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />,
  queued: <Clock className="h-4 w-4 text-muted-foreground" />,
};

export default function RepoDetailPage() {
  const { projectId, repoId } = useParams<{ projectId: string; repoId: string }>();
  const qc = useQueryClient();

  const [selectedBranches, setSelectedBranches] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [sprintAlign, setSprintAlign] = useState<string>("");
  const [contribSearch, setContribSearch] = useState("");
  const [contribSort, setContribSort] = useState<{ key: "name" | "email" | "lines"; dir: "asc" | "desc" }>({ key: "name", dir: "asc" });
  const [showInactive, setShowInactive] = useState(false);
  const [drillDown, setDrillDown] = useState<{ title: string; metric: string } | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [filesBranchOverride, setFilesBranchOverride] = useState<string | null>(null);
  const [commitPage, setCommitPage] = useState(1);
  const [commitSearch, setCommitSearch] = useState("");
  const debouncedSearch = useDebouncedValue(commitSearch);
  const [activeTab, setActiveTab] = useState<string>("commits");
  const [commitBranch, setCommitBranch] = useState<string | undefined>(undefined);

  const { data: iterations = [] } = useIterations(projectId);

  const handleSprintAlign = (iterationId: string) => {
    setSprintAlign(iterationId);
    if (iterationId === "__none__") return;
    const iter = iterations.find(i => i.id === iterationId);
    if (iter?.start_date && iter?.end_date) {
      setDateRange({ from: iter.start_date, to: iter.end_date });
    }
  };

  const branchParam = selectedBranches.length > 0 ? selectedBranches : undefined;

  const { data: repo } = useRepo(repoId);
  const { data: stats } = useRepoStats(repoId, { branches: branchParam, from: dateRange.from, to: dateRange.to });

  const dailyParams = useMemo(() => ({
    repository_id: repoId,
    branch: branchParam,
    from_date: dateRange.from,
    to_date: dateRange.to,
  }), [repoId, branchParam, dateRange]);
  const { data: daily = [] } = useDailyStats(dailyParams);

  const { data: syncJobs = [] } = useSyncJobs(repoId);
  const syncing = syncJobs.some((j) => j.status === "queued" || j.status === "running");
  const liveJobId = syncJobs.find((j) => j.status === "queued" || j.status === "running")?.id ?? null;
  const { data: branches = [] } = useRepoBranches(repoId);
  const { data: contributors = [] } = useRepoContributors(repoId, branchParam);
  const filesBranch = filesBranchOverride ?? repo?.default_branch ?? undefined;
  const { data: fileTree = [] } = useFileTree(repoId, filesBranch);

  const commitFilters = useMemo(() => ({
    branch: commitBranch ? [commitBranch] : undefined,
    search: debouncedSearch || undefined,
    page: commitPage,
    per_page: 30,
  }), [commitBranch, debouncedSearch, commitPage]);
  const { data: commits, isLoading: commitsLoading } = useRepoCommits(repoId, commitFilters);

  const syncMutation = useSyncRepo();
  const cancelMutation = useCancelSync(repoId);

  const wasSyncing = useRef(false);
  useEffect(() => {
    if (syncing) {
      wasSyncing.current = true;
    } else if (wasSyncing.current) {
      wasSyncing.current = false;
      qc.invalidateQueries({ queryKey: queryKeys.repos.detail(repoId) });
      qc.invalidateQueries({ queryKey: queryKeys.repos.stats(repoId) });
      qc.invalidateQueries({ queryKey: queryKeys.repos.branches(repoId) });
      qc.invalidateQueries({ queryKey: queryKeys.repos.contributors(repoId) });
      qc.invalidateQueries({ queryKey: queryKeys.repos.fileTree(repoId) });
      qc.invalidateQueries({ queryKey: queryKeys.daily(dailyParams) });
    }
  }, [syncing, repoId, qc, dailyParams]);

  async function handleSync() {
    if (syncing) return;
    try {
      await syncMutation.mutateAsync(repoId);
    } catch { /* mutation error handled by React Query */ }
  }

  async function handleCancel() {
    const jobId = liveJobId;
    if (!jobId) return;
    await cancelMutation.mutateAsync(jobId);
  }

  const chartData = useMemo(() => daily.map((d) => ({
    date: d.date.slice(5),
    lines_added: d.lines_added,
    lines_deleted: d.lines_deleted,
    commits: d.commits,
  })), [daily]);

  const authorData = useMemo(() => {
    const authorMap = new Map<string, { name: string; commits: number; lines_added: number; lines_deleted: number }>();
    daily.forEach((d) => {
      const c = contributors.find((c) => c.id === d.contributor_id);
      const name = c?.canonical_name || "Unknown";
      const existing = authorMap.get(d.contributor_id) || { name, commits: 0, lines_added: 0, lines_deleted: 0 };
      existing.commits += d.commits;
      existing.lines_added += d.lines_added;
      existing.lines_deleted += d.lines_deleted;
      authorMap.set(d.contributor_id, existing);
    });
    return Array.from(authorMap.values())
      .sort((a, b) => (b.lines_added + b.lines_deleted) - (a.lines_added + a.lines_deleted))
      .slice(0, 10);
  }, [daily, contributors]);

  const contribStatsMap = useMemo(() => {
    const map = new Map<string, { added: number; deleted: number; sparkline: number[] }>();
    const byContribDate = new Map<string, Map<string, number>>();
    daily.forEach((d) => {
      const existing = map.get(d.contributor_id) || { added: 0, deleted: 0, sparkline: [] };
      existing.added += d.lines_added;
      existing.deleted += d.lines_deleted;
      map.set(d.contributor_id, existing);
      if (!byContribDate.has(d.contributor_id)) byContribDate.set(d.contributor_id, new Map());
      const dateMap = byContribDate.get(d.contributor_id)!;
      const dateKey = d.date.slice(0, 10);
      dateMap.set(dateKey, (dateMap.get(dateKey) || 0) + d.lines_added + d.lines_deleted);
    });
    const allDates = [...new Set(daily.map((d) => d.date.slice(0, 10)))].sort();
    const recentDates = allDates.slice(-30);
    for (const [cid, entry] of map) {
      const dateMap = byContribDate.get(cid) || new Map();
      entry.sparkline = recentDates.map((d) => dateMap.get(d) || 0);
    }
    return map;
  }, [daily]);

  useRegisterUIContext("repo-detail", repo ? {
    repo_id: repoId,
    name: repo.name,
    platform: repo.platform,
    default_branch: repo.default_branch,
    stats: stats ? {
      total_commits: stats.total_commits,
      contributor_count: stats.contributor_count,
      bus_factor: stats.bus_factor,
      churn_ratio: stats.churn_ratio,
      pr_cycle_time_hours: stats.pr_cycle_time_hours,
      pr_review_turnaround_hours: stats.pr_review_turnaround_hours,
    } : null,
    contributor_count: contributors.length,
  } : null);

  if (!repo) return (
    <div className="space-y-6">
      <FilterBarSkeleton />
      <StatRowSkeleton />
      <StatRowSkeleton />
      <ChartSkeleton />
      <TableSkeleton rows={5} cols={4} />
    </div>
  );

  const hasActivity = (id: string) => {
    const cs = contribStatsMap.get(id);
    return cs ? cs.added + cs.deleted > 0 : false;
  };

  const sortContribs = (list: ContributorSummary[]) =>
    list.sort((a, b) => {
      if (contribSort.key === "lines") {
        const aTotal = (contribStatsMap.get(a.id)?.added || 0) + (contribStatsMap.get(a.id)?.deleted || 0);
        const bTotal = (contribStatsMap.get(b.id)?.added || 0) + (contribStatsMap.get(b.id)?.deleted || 0);
        return contribSort.dir === "asc" ? aTotal - bTotal : bTotal - aTotal;
      }
      const valA = contribSort.key === "name" ? a.canonical_name : a.canonical_email;
      const valB = contribSort.key === "name" ? b.canonical_name : b.canonical_email;
      const cmp = valA.localeCompare(valB);
      return contribSort.dir === "asc" ? cmp : -cmp;
    });

  const filtered = contributors.filter((c) => {
    if (!contribSearch) return true;
    const q = contribSearch.toLowerCase();
    return c.canonical_name.toLowerCase().includes(q) || c.canonical_email.toLowerCase().includes(q);
  });
  const activeContribs = sortContribs(filtered.filter((c) => hasActivity(c.id)));
  const inactiveContribs = sortContribs(filtered.filter((c) => !hasActivity(c.id)));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{repo.name}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="secondary">{repo.platform}</Badge>
            {repo.platform_owner && <span>{repo.platform_owner}/{repo.platform_repo}</span>}
            <span className="text-border">|</span>
            <GitBranch className="h-3.5 w-3.5" />
            <Select
              value={repo.default_branch || ""}
              onValueChange={async (v) => {
                await api.updateRepo(repoId, { default_branch: v });
                qc.invalidateQueries({ queryKey: queryKeys.repos.detail(repoId) });
              }}
            >
              <SelectTrigger className="h-6 w-auto gap-1 border-none bg-transparent px-1 text-xs font-medium shadow-none">
                <SelectValue placeholder="Set default branch" />
              </SelectTrigger>
              <SelectContent>
                {branches.map((b) => (
                  <SelectItem key={b.id} value={b.name}>{b.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {syncing ? (
            <>
              <Button disabled><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Syncing...</Button>
              <Button variant="destructive" onClick={handleCancel}><XCircle className="mr-2 h-4 w-4" /> Cancel</Button>
            </>
          ) : (
            <Button onClick={handleSync}><RefreshCw className="mr-2 h-4 w-4" /> Sync Now</Button>
          )}
        </div>
      </div>

      {syncing && liveJobId && (
        <SyncLogViewer repoId={repoId} jobId={liveJobId} onDone={() => { qc.invalidateQueries({ queryKey: queryKeys.repos.syncJobs(repoId) }); }} />
      )}

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        {branches.length > 0 && (
          <BranchMultiSelect branches={branches} selected={selectedBranches} onChange={setSelectedBranches} />
        )}
        <div className="h-6 w-px bg-border" />
        {iterations.length > 0 && (
          <Select value={sprintAlign} onValueChange={handleSprintAlign}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Align to Sprint" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">No Sprint</SelectItem>
              {iterations.map(it => (
                <SelectItem key={it.id} value={it.id}>
                  {it.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      {stats && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard className={ANIM_CARD} style={stagger(0)} title="Total Commits" value={stats.total_commits} tooltip="Total number of commits in this repository for the selected period" onClick={() => setDrillDown({ title: "Total Commits", metric: "commits" })} />
            <StatCard className={ANIM_CARD} style={stagger(1)} title="Contributors" value={stats.contributor_count} tooltip="Number of unique people who made commits in the selected period" onClick={() => setDrillDown({ title: "Contributors", metric: "contributors" })} />
            <StatCard className={ANIM_CARD} style={stagger(2)} title="Bus Factor" value={stats.bus_factor} subtitle="50% commit threshold" tooltip="Minimum number of contributors whose combined work accounts for 50% of all commits." onClick={() => setDrillDown({ title: "Bus Factor", metric: "bus_factor" })} />
            <StatCard className={ANIM_CARD} style={stagger(3)} title="Commits/Day (7d)" value={stats.trends.avg_commits_7d} trend={stats.trends.wow_commits_delta} tooltip="Average number of commits per day over the last 7 days." onClick={() => setDrillDown({ title: "Commits/Day (7d)", metric: "commits_per_day" })} />
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard className={ANIM_CARD} style={stagger(4)} title="PR Cycle Time" value={`${stats.pr_cycle_time_hours}h`} subtitle="Avg open to merge" tooltip="Average time from when a pull request is opened to when it gets merged." />
            <StatCard className={ANIM_CARD} style={stagger(5)} title="Review Turnaround" value={`${stats.pr_review_turnaround_hours}h`} subtitle="Avg to first review" tooltip="Average time from when a pull request is opened until it receives its first code review." />
            <StatCard className={ANIM_CARD} style={stagger(6)} title="Churn Ratio" value={stats.churn_ratio} subtitle="Deleted / added lines" tooltip="Ratio of lines deleted to lines added." onClick={() => setDrillDown({ title: "Churn Ratio", metric: "churn" })} />
            <StatCard className={ANIM_CARD} style={stagger(7)} title="Work Distribution" value={stats.contribution_gini} subtitle="Gini (0=even, 1=concentrated)" tooltip="Measures how evenly work is spread across contributors." onClick={() => setDrillDown({ title: "Work Distribution", metric: "work_distribution" })} />
          </div>

          <StatDetailSheet
            open={!!drillDown}
            onOpenChange={(v) => { if (!v) setDrillDown(null); }}
            title={drillDown?.title ?? ""}
            metric={drillDown?.metric ?? "commits"}
            daily={daily}
            contributorNames={Object.fromEntries(contributors.map((c) => [c.id, c.canonical_name]))}
            repoNames={repo ? { [repo.id]: repo.name } : {}}
          />
        </>
      )}

      {chartData.length > 0 ? (
        <ContributionAreaChart data={chartData} title="Activity" />
      ) : (
        <p className="text-sm text-muted-foreground">No activity data for this period.</p>
      )}
      {authorData.length > 0 && <AuthorBarChart data={authorData} />}

      {contributors.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Contributors</h2>
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Filter by name or email..." value={contribSearch} onChange={(e) => setContribSearch(e.target.value)} className="pl-9" />
            </div>
          </div>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => setContribSort((s) => ({ key: "name", dir: s.key === "name" && s.dir === "asc" ? "desc" : "asc" }))}>
                      Name <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => setContribSort((s) => ({ key: "email", dir: s.key === "email" && s.dir === "asc" ? "desc" : "asc" }))}>
                      Email <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button className="flex items-center gap-1 hover:text-foreground" onClick={() => setContribSort((s) => ({ key: "lines", dir: s.key === "lines" && s.dir === "desc" ? "asc" : "desc" }))}>
                      +/- Lines <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </TableHead>
                  <TableHead className="w-32">Activity (30d)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeContribs.map((c) => {
                  const cs = contribStatsMap.get(c.id);
                  return (
                    <TableRow key={c.id}>
                      <TableCell>
                        <Link href={`/contributors/${c.id}`} className="flex items-center gap-2 font-medium hover:underline">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">{c.canonical_name.charAt(0).toUpperCase()}</div>
                          {c.canonical_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{c.canonical_email}</TableCell>
                      <TableCell className="text-xs whitespace-nowrap">
                        <span className="text-emerald-500">+{(cs?.added || 0).toLocaleString()}</span>{" / "}<span className="text-red-500">-{(cs?.deleted || 0).toLocaleString()}</span>
                      </TableCell>
                      <TableCell>
                        <div className="h-8 w-28"><MiniSparkline data={cs!.sparkline} color="var(--chart-1)" /></div>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {activeContribs.length === 0 && inactiveContribs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="py-6 text-center text-muted-foreground">
                      {contribSearch ? `No contributors match "${contribSearch}"` : "No contributors found"}
                    </TableCell>
                  </TableRow>
                )}
                {inactiveContribs.length > 0 && (
                  <>
                    <TableRow>
                      <TableCell colSpan={4} className="p-0">
                        <button onClick={() => setShowInactive((v) => !v)} className="flex w-full items-center gap-2 px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                          {showInactive ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                          {inactiveContribs.length} inactive contributor{inactiveContribs.length !== 1 ? "s" : ""}
                        </button>
                      </TableCell>
                    </TableRow>
                    {showInactive && inactiveContribs.map((c) => (
                      <TableRow key={c.id} className="text-muted-foreground">
                        <TableCell>
                          <Link href={`/contributors/${c.id}`} className="flex items-center gap-2 font-medium hover:underline">
                            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">{c.canonical_name.charAt(0).toUpperCase()}</div>
                            {c.canonical_name}
                          </Link>
                        </TableCell>
                        <TableCell>{c.canonical_email}</TableCell>
                        <TableCell className="text-xs">+0 / -0</TableCell>
                        <TableCell><span className="text-[10px]">No activity</span></TableCell>
                      </TableRow>
                    ))}
                  </>
                )}
              </TableBody>
            </Table>
          </Card>
        </>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <div className="flex items-center gap-3">
          <TabsList>
            <TabsTrigger value="commits" className="gap-2"><GitCommitHorizontal className="h-4 w-4" /> Commits</TabsTrigger>
            <TabsTrigger value="files" className="gap-2"><FileCode2 className="h-4 w-4" /> Files</TabsTrigger>
            <TabsTrigger value="hotspots" className="gap-2"><Flame className="h-4 w-4" /> Hotspots</TabsTrigger>
            <TabsTrigger value="security" className="gap-2"><ShieldAlert className="h-4 w-4" /> Security</TabsTrigger>
            <TabsTrigger value="dependencies" className="gap-2"><Package className="h-4 w-4" /> Dependencies</TabsTrigger>
          </TabsList>

          {activeTab === "commits" && branches.length > 0 && (
            <Select value={commitBranch ?? "__all__"} onValueChange={(v) => { setCommitBranch(v === "__all__" ? undefined : v); setCommitPage(1); }}>
              <SelectTrigger className="w-48 h-9">
                <GitBranch className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All branches</SelectItem>
                {branches.map((b) => (
                  <SelectItem key={b.id} value={b.name}>{b.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {activeTab === "hotspots" && branches.length > 0 && (
            <Select value={filesBranch ?? "__all__"} onValueChange={(v) => { setFilesBranchOverride(v === "__all__" ? null : v); }}>
              <SelectTrigger className="w-48 h-9">
                <GitBranch className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All branches</SelectItem>
                {branches.map((b) => (
                  <SelectItem key={b.id} value={b.name}>{b.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {activeTab === "commits" && (
            <div className="relative ml-auto w-72">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search commit messages..."
                value={commitSearch}
                onChange={(e) => { setCommitSearch(e.target.value); setCommitPage(1); }}
                className="h-8 pl-8 text-sm"
              />
            </div>
          )}
        </div>

        <TabsContent value="commits">
          {commits && (
            <CommitList
              commits={commits.items}
              total={commits.total}
              page={commitPage}
              perPage={commits.per_page}
              loading={commitsLoading}
              onPageChange={setCommitPage}
            />
          )}
        </TabsContent>

        <TabsContent value="files">
          <div className="grid gap-4 lg:grid-cols-2">
            <FileTree nodes={fileTree} onSelectFile={setSelectedFile} selectedPath={selectedFile ?? undefined} />
            {selectedFile ? (
              <FileDetailPanel repoId={repoId} filePath={selectedFile} branch={filesBranch} />
            ) : (
              <div className="flex items-center justify-center rounded-lg border border-dashed p-12 text-sm text-muted-foreground">
                Select a file to view contributor details
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="hotspots">
          <HotspotTable repoId={repoId} branch={filesBranch} onSelectFile={(p) => setSelectedFile(p)} />
        </TabsContent>

        <TabsContent value="security">
          <RepoSecuritySection repoId={repoId} />
        </TabsContent>

        <TabsContent value="dependencies">
          <RepoDependenciesSection repoId={repoId} />
        </TabsContent>
      </Tabs>

      <div>
        <h2 className="mb-3 text-xl font-semibold">Recent Sync Jobs</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Finished</TableHead>
                <TableHead>Error</TableHead>
                <TableHead className="w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syncJobs.map((j) => (
                <TableRow key={j.id}>
                  <TableCell className="align-top">
                    <span className="inline-flex items-center gap-2">
                      {STATUS_ICON[j.status] || null}
                      <span className="capitalize">{j.status}</span>
                    </span>
                  </TableCell>
                  <TableCell className="align-top">{j.started_at ? new Date(j.started_at).toLocaleString() : "-"}</TableCell>
                  <TableCell className="align-top">{j.finished_at ? new Date(j.finished_at).toLocaleString() : "-"}</TableCell>
                  <TableCell className="align-top max-w-xs truncate text-destructive">{j.error_message || "-"}</TableCell>
                  <TableCell className="align-top">
                    <ViewLogsButton repoId={repoId} jobId={j.id} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    </div>
  );
}

const SEVERITY_CONFIG: Record<string, { icon: typeof ShieldAlert; color: string; bg: string }> = {
  critical: { icon: ShieldAlert, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30" },
  high: { icon: AlertTriangle, color: "text-orange-500", bg: "bg-orange-50 dark:bg-orange-950/30" },
  medium: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-50 dark:bg-amber-950/30" },
  low: { icon: Info, color: "text-blue-500", bg: "bg-blue-50 dark:bg-blue-950/30" },
  info: { icon: Info, color: "text-slate-400", bg: "bg-slate-50 dark:bg-slate-950/30" },
};

function formatRelative(dateStr: string | null) {
  if (!dateStr) return "N/A";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function SecurityFindingRow({
  finding,
  onDismiss,
  onFalsePositive,
}: {
  finding: SastFinding;
  onDismiss: (id: string) => void;
  onFalsePositive: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  const SevIcon = config.icon;
  const ruleShort = finding.rule_id.split(".").slice(-2).join(".");

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className={`border-l-4 ${
        finding.severity === "critical" ? "border-l-red-500" :
        finding.severity === "high" ? "border-l-orange-500" :
        finding.severity === "medium" ? "border-l-amber-500" :
        finding.severity === "low" ? "border-l-blue-500" : "border-l-slate-300"
      }`}>
        <CollapsibleTrigger asChild>
          <CardContent className="flex items-start gap-3 py-3 px-4 cursor-pointer hover:bg-muted/30 transition-colors">
            <div className={`rounded-md p-1.5 mt-0.5 ${config.bg}`}>
              <SevIcon className={`h-4 w-4 ${config.color}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-sm">{finding.message}</span>
                <Badge variant="outline" className="text-xs font-mono">{ruleShort}</Badge>
                {finding.cwe_ids?.map((c) => (
                  <Badge key={c} variant="secondary" className="text-xs">{c}</Badge>
                ))}
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <FileCode2 className="h-3 w-3" />
                  {finding.file_path}:{finding.start_line}
                </span>
                <span>First seen: {formatRelative(finding.first_detected_at)}</span>
                <Badge variant="outline" className="text-xs capitalize">{finding.confidence}</Badge>
              </div>
            </div>
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </CardContent>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t px-4 py-3 space-y-3 bg-muted/10">
            {finding.code_snippet && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Vulnerable Code</p>
                <pre className="text-xs bg-muted rounded-md p-3 overflow-x-auto font-mono"><code>{finding.code_snippet}</code></pre>
              </div>
            )}
            {finding.fix_suggestion && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Suggested Fix</p>
                <pre className="text-xs bg-emerald-50 dark:bg-emerald-950/20 rounded-md p-3 overflow-x-auto font-mono border border-emerald-200 dark:border-emerald-800"><code>{finding.fix_suggestion}</code></pre>
              </div>
            )}
            {finding.metadata && !!(finding.metadata as Record<string, unknown>).references && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">References:</span>
                {((finding.metadata as Record<string, unknown>).references as string[]).slice(0, 3).map((ref) => (
                  <a key={ref} href={ref} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline flex items-center gap-0.5">
                    {new URL(ref).hostname}<ExternalLink className="h-3 w-3" />
                  </a>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2 pt-1">
              <Button variant="outline" size="sm" className="text-xs" onClick={() => onDismiss(finding.id)}>
                <EyeOff className="h-3 w-3 mr-1" />Dismiss
              </Button>
              <Button variant="outline" size="sm" className="text-xs" onClick={() => onFalsePositive(finding.id)}>
                <XCircle className="h-3 w-3 mr-1" />False Positive
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

function RepoSecuritySection({ repoId }: { repoId: string }) {
  const qc = useQueryClient();
  const { data: summary } = useSastSummary(repoId);
  const { data: findings, isLoading } = useSastFindings(repoId);
  const { data: runs } = useSastRuns(repoId);
  const [severityFilter, setSeverityFilter] = useState("");

  const lastRun = runs?.[0];
  const { activeRunId: scanningRunId, startTracking: startScanTracking, stopTracking: stopScanTracking } = useActiveRunTracking(lastRun);

  async function handleScan() {
    if (scanningRunId) return;
    try {
      const run = await api.triggerSastScan(repoId);
      startScanTracking(run.id);
    } catch { /* ignore */ }
  }

  function handleScanDone() {
    stopScanTracking();
    qc.invalidateQueries({ queryKey: queryKeys.sast.findings(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.summary(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.runs(repoId, "repo") });
  }

  async function handleDismiss(findingId: string) {
    await api.dismissSastFinding(repoId, findingId);
    qc.invalidateQueries({ queryKey: queryKeys.sast.findings(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.summary(repoId, "repo") });
  }

  async function handleFalsePositive(findingId: string) {
    await api.markSastFalsePositive(repoId, findingId);
    qc.invalidateQueries({ queryKey: queryKeys.sast.findings(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.summary(repoId, "repo") });
  }

  function handleReportDownload(format: string) {
    const token = api.getAuthToken();
    const baseUrl = api.getSastReportUrl(repoId, format);
    const url = token ? `${baseUrl}&token=${encodeURIComponent(token)}` : baseUrl;
    window.open(url, "_blank");
  }

  const score = summary
    ? Math.max(0, 100 - (summary.critical * 20) - (summary.high * 10) - (summary.medium * 3) - (summary.low * 1))
    : null;
  const scoreColor = score === null ? "bg-muted" : score >= 80 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";

  const filteredFindings = severityFilter
    ? findings?.filter((f) => f.severity === severityFilter)
    : findings;

  const sevCards: { label: string; value: number; icon: typeof ShieldAlert; color: string }[] = summary ? [
    { label: "Critical", value: summary.critical, icon: ShieldAlert, color: "text-red-600" },
    { label: "High", value: summary.high, icon: AlertTriangle, color: "text-orange-500" },
    { label: "Medium", value: summary.medium, icon: AlertCircle, color: "text-amber-500" },
    { label: "Low", value: summary.low, icon: Info, color: "text-blue-500" },
    { label: "Fixed (30d)", value: summary.fixed_30d, icon: TrendingDown, color: "text-emerald-500" },
    { label: "Total Open", value: summary.total_open, icon: Bug, color: "text-slate-500" },
  ] : [];

  return (
    <div className="space-y-4">
      {/* Score banner + actions */}
      <Card>
        <CardContent className="flex items-center justify-between py-4 px-6 gap-4">
          <div className="flex items-center gap-4">
            <div className={`h-12 w-12 rounded-full ${scoreColor} flex items-center justify-center`}>
              <span className="text-white font-bold text-lg">{score ?? "?"}</span>
            </div>
            <div>
              <p className="font-semibold text-lg">Security Score</p>
              <p className="text-sm text-muted-foreground">
                {lastRun ? `Last scan: ${formatRelative(lastRun.created_at)}` : "No scans yet"}
              </p>
            </div>
            {score !== null && (
              <div className="hidden sm:flex items-center gap-1 ml-4">
                <div className="h-2 w-48 rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${scoreColor}`} style={{ width: `${score}%` }} />
                </div>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleScan} disabled={!!scanningRunId}>
              {scanningRunId ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" />Scanning...</>
              ) : (
                <><Play className="h-4 w-4 mr-1" />Run Scan</>
              )}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm"><Download className="h-4 w-4 mr-1" /> Report</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleReportDownload("json")}>Download JSON</DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleReportDownload("csv")}>Download CSV</DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleReportDownload("pdf")}>Download PDF</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardContent>
      </Card>

      {/* Scan log viewer */}
      {scanningRunId && (
        <SyncLogViewer
          logUrl={`${api.getApiBase()}/repositories/${repoId}/sast/runs/${scanningRunId}/logs`}
          compact
          title="SAST Scan Logs"
          onDone={handleScanDone}
        />
      )}

      {/* Severity cards */}
      {summary && (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          {sevCards.map((c) => (
            <Card key={c.label}>
              <CardContent className="flex items-center gap-3 py-4 px-4">
                <c.icon className={`h-7 w-7 ${c.color}`} />
                <div>
                  <p className="text-2xl font-bold">{c.value}</p>
                  <p className="text-xs text-muted-foreground">{c.label}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Severity filter */}
      <div className="flex items-center gap-1 rounded-lg bg-muted p-1 w-fit">
        {[{ v: "", l: "All" }, { v: "critical", l: "Critical" }, { v: "high", l: "High" }, { v: "medium", l: "Medium" }, { v: "low", l: "Low" }].map((s) => (
          <button
            key={s.v}
            onClick={() => setSeverityFilter(s.v)}
            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
              severityFilter === s.v ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {s.l}
          </button>
        ))}
      </div>

      {/* Findings list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : filteredFindings && filteredFindings.length > 0 ? (
        <div className="space-y-2">
          {filteredFindings.map((f) => (
            <SecurityFindingRow key={f.id} finding={f} onDismiss={handleDismiss} onFalsePositive={handleFalsePositive} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <ShieldCheck className="h-10 w-10 mb-2 text-emerald-500" />
            <p className="font-medium">No security findings</p>
            <p className="text-sm mt-1">
              {runs?.length ? "All clear! No open vulnerabilities detected." : "Run a SAST scan to check for vulnerabilities."}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Top rules & files */}
      {summary && (Object.keys(summary.by_rule).length > 0 || Object.keys(summary.by_file).length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          {Object.keys(summary.by_rule).length > 0 && (
            <Card>
              <CardHeader className="py-3 px-4"><CardTitle className="text-sm font-medium">Top Rules</CardTitle></CardHeader>
              <CardContent className="pt-0 px-4 pb-3">
                <Table>
                  <TableHeader><TableRow><TableHead>Rule</TableHead><TableHead className="text-right">Count</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {Object.entries(summary.by_rule).map(([rule, count]) => (
                      <TableRow key={rule}><TableCell className="font-mono text-xs">{rule}</TableCell><TableCell className="text-right">{count}</TableCell></TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
          {Object.keys(summary.by_file).length > 0 && (
            <Card>
              <CardHeader className="py-3 px-4"><CardTitle className="text-sm font-medium">Most Affected Files</CardTitle></CardHeader>
              <CardContent className="pt-0 px-4 pb-3">
                <Table>
                  <TableHeader><TableRow><TableHead>File</TableHead><TableHead className="text-right">Findings</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {Object.entries(summary.by_file).map(([file, count]) => (
                      <TableRow key={file}><TableCell className="font-mono text-xs truncate max-w-md">{file}</TableCell><TableCell className="text-right">{count}</TableCell></TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Scan history */}
      {runs && runs.length > 0 && (
        <div>
          <h2 className="mb-3 text-xl font-semibold">Scan History</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Commit</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.slice(0, 10).map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="flex items-center gap-2">
                      {SCAN_STATUS_ICON[run.status] || null}
                      <span className="capitalize">{run.status}</span>
                    </TableCell>
                    <TableCell>{run.created_at ? new Date(run.created_at).toLocaleString() : "-"}</TableCell>
                    <TableCell>{run.findings_count}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{run.commit_sha ? run.commit_sha.slice(0, 7) : "-"}</TableCell>
                    <TableCell className="max-w-xs truncate text-destructive">{run.error_message || "-"}</TableCell>
                    <TableCell>
                      <ViewLogsButton logUrl={`${api.getApiBase()}/repositories/${repoId}/sast/runs/${run.id}/logs`} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Repo Dependencies Section
// ---------------------------------------------------------------------------

const DEP_ECOSYSTEM_COLORS: Record<string, string> = {
  PyPI: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  npm: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  Go: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300",
  "crates.io": "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  Docker: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  Maven: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  NuGet: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
  RubyGems: "bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-300",
};

function RepoDependenciesSection({ repoId }: { repoId: string }) {
  const qc = useQueryClient();
  const { data: summary } = useDepSummary(repoId);
  const { data: findingsPage, isLoading } = useDepFindings(repoId);
  const findings = findingsPage?.items;
  const { data: runs } = useDepRuns(repoId);
  const [viewFilter, setViewFilter] = useState<"all" | "vulnerable" | "outdated">("all");

  const lastRun = runs?.[0];
  const { activeRunId: scanningRunId, startTracking: startDepTracking, stopTracking: stopDepTracking } = useActiveRunTracking(lastRun);

  async function handleScan() {
    if (scanningRunId) return;
    try {
      const run = await api.triggerDepScan(repoId);
      startDepTracking(run.id);
    } catch { /* ignore */ }
  }

  function handleScanDone() {
    stopDepTracking();
    qc.invalidateQueries({ queryKey: queryKeys.dependencies.findings(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.dependencies.summary(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.dependencies.runs(repoId, "repo") });
  }

  async function handleDismiss(findingId: string) {
    await api.dismissDepFinding(repoId, findingId);
    qc.invalidateQueries({ queryKey: queryKeys.dependencies.findings(repoId, "repo") });
    qc.invalidateQueries({ queryKey: queryKeys.dependencies.summary(repoId, "repo") });
  }

  function handleReportDownload(format: string) {
    const token = api.getAuthToken();
    const baseUrl = api.getDepReportUrl(repoId, format);
    const url = token ? `${baseUrl}&token=${encodeURIComponent(token)}` : baseUrl;
    window.open(url, "_blank");
  }

  const score = summary && summary.total_packages > 0
    ? Math.round((summary.up_to_date / summary.total_packages) * 100)
    : null;
  const scoreColor = score === null ? "bg-muted" : score >= 80 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";

  const filteredFindings = findings?.filter((f) => {
    if (viewFilter === "vulnerable") return f.is_vulnerable;
    if (viewFilter === "outdated") return f.is_outdated;
    return true;
  });

  const byFile = new Map<string, DepFinding[]>();
  (filteredFindings || []).forEach((f) => {
    const list = byFile.get(f.file_path) || [];
    list.push(f);
    byFile.set(f.file_path, list);
  });

  return (
    <div className="space-y-4">
      {/* Score banner + actions */}
      <Card>
        <CardContent className="flex items-center justify-between py-4 px-6 gap-4">
          <div className="flex items-center gap-4">
            <div className={`h-12 w-12 rounded-full ${scoreColor} flex items-center justify-center`}>
              <span className="text-white font-bold text-lg">{score ?? "?"}</span>
            </div>
            <div>
              <p className="font-semibold text-lg">Dependency Health</p>
              <p className="text-sm text-muted-foreground">
                {lastRun ? `Last scan: ${formatRelative(lastRun.created_at)}` : "No scans yet"}
              </p>
            </div>
            {score !== null && (
              <div className="hidden sm:flex items-center gap-1 ml-4">
                <div className="h-2 w-48 rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${scoreColor}`} style={{ width: `${score}%` }} />
                </div>
                <span className="text-xs text-muted-foreground ml-1">{score}% healthy</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleScan} disabled={!!scanningRunId}>
              {scanningRunId ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" />Scanning...</>
              ) : (
                <><Play className="h-4 w-4 mr-1" />Run Scan</>
              )}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm"><Download className="h-4 w-4 mr-1" /> Report</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleReportDownload("json")}>Download JSON</DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleReportDownload("csv")}>Download CSV</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardContent>
      </Card>

      {/* Scan log viewer */}
      {scanningRunId && (
        <SyncLogViewer
          logUrl={`${api.getApiBase()}/repositories/${repoId}/dependencies/runs/${scanningRunId}/logs`}
          compact
          title="Dependency Scan Logs"
          onDone={handleScanDone}
        />
      )}

      {/* Summary cards */}
      {summary && (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
          <Card>
            <CardContent className="flex items-center gap-3 py-4 px-4">
              <Package className="h-7 w-7 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{summary.total_packages}</p>
                <p className="text-xs text-muted-foreground">Total Packages</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 py-4 px-4">
              <ShieldAlert className="h-7 w-7 text-red-500" />
              <div>
                <p className="text-2xl font-bold text-red-600">{summary.vulnerable}</p>
                <p className="text-xs text-muted-foreground">Vulnerable</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 py-4 px-4">
              <ArrowUpCircle className="h-7 w-7 text-amber-500" />
              <div>
                <p className="text-2xl font-bold text-amber-600">{summary.outdated}</p>
                <p className="text-xs text-muted-foreground">Outdated</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 py-4 px-4">
              <CheckCircle2 className="h-7 w-7 text-emerald-500" />
              <div>
                <p className="text-2xl font-bold text-emerald-600">{summary.up_to_date}</p>
                <p className="text-xs text-muted-foreground">Up to Date</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* View filter */}
      <div className="flex items-center gap-1 rounded-lg bg-muted p-1 w-fit">
        {([
          { v: "all" as const, l: "All" },
          { v: "vulnerable" as const, l: "Vulnerable" },
          { v: "outdated" as const, l: "Outdated" },
        ]).map((s) => (
          <button
            key={s.v}
            onClick={() => setViewFilter(s.v)}
            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
              viewFilter === s.v ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {s.l}
          </button>
        ))}
      </div>

      {/* Findings grouped by file */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : byFile.size > 0 ? (
        <div className="space-y-4">
          {Array.from(byFile.entries()).map(([filePath, deps]) => (
            <Card key={filePath}>
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-sm font-medium font-mono flex items-center gap-2">
                  <FileCode2 className="h-4 w-4 text-muted-foreground" />
                  {filePath}
                  <Badge variant="outline" className={`text-xs ml-2 ${DEP_ECOSYSTEM_COLORS[deps[0]?.ecosystem] || ""}`}>
                    {deps[0]?.ecosystem}
                  </Badge>
                  <span className="text-muted-foreground font-normal ml-auto">{deps.length} packages</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0 px-4 pb-3">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Package</TableHead>
                      <TableHead>Current</TableHead>
                      <TableHead>Latest</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="w-16"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {deps.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="font-medium">{d.package_name}</TableCell>
                        <TableCell className="font-mono text-xs">{d.current_version || "—"}</TableCell>
                        <TableCell className="font-mono text-xs">{d.latest_version || "—"}</TableCell>
                        <TableCell>
                          {d.is_vulnerable ? (
                            <Badge variant="destructive" className="text-xs">
                              {(d.vulnerabilities?.length || 0)} vuln{(d.vulnerabilities?.length || 0) !== 1 ? "s" : ""}
                            </Badge>
                          ) : d.is_outdated ? (
                            <Badge variant="secondary" className="text-xs">outdated</Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs text-emerald-600">up to date</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="sm" onClick={() => handleDismiss(d.id)}>
                            <EyeOff className="h-3.5 w-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Package className="h-10 w-10 mb-2 text-emerald-500" />
            <p className="font-medium">No dependency findings</p>
            <p className="text-sm mt-1">
              {runs?.length ? "No dependency issues found." : "Run a scan to analyze dependencies."}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Scan history */}
      {runs && runs.length > 0 && (
        <div>
          <h2 className="mb-3 text-xl font-semibold">Scan History</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Packages</TableHead>
                  <TableHead>Vulnerable</TableHead>
                  <TableHead>Outdated</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.slice(0, 10).map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="flex items-center gap-2">
                      {SCAN_STATUS_ICON[run.status] || null}
                      <span className="capitalize">{run.status}</span>
                    </TableCell>
                    <TableCell>{run.created_at ? new Date(run.created_at).toLocaleString() : "-"}</TableCell>
                    <TableCell>{run.findings_count}</TableCell>
                    <TableCell>{run.vulnerable_count}</TableCell>
                    <TableCell>{run.outdated_count}</TableCell>
                    <TableCell className="max-w-xs truncate text-destructive">{run.error_message || "-"}</TableCell>
                    <TableCell>
                      <ViewLogsButton logUrl={`${api.getApiBase()}/repositories/${repoId}/dependencies/runs/${run.id}/logs`} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
      )}
    </div>
  );
}
