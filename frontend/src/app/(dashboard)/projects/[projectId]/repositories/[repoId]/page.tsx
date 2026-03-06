"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMemo } from "react";
import { RefreshCw, AlertCircle, CheckCircle2, Clock, Loader2, XCircle, Ban, Search, ArrowUpDown, ChevronDown, ChevronRight, FileCode2, Flame, GitBranch, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatCard } from "@/components/stat-card";
import { StatDetailSheet } from "@/components/stat-detail-sheet";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { AuthorBarChart } from "@/components/charts/author-bar-chart";
import { FileTree } from "@/components/file-tree";
import { FileDetailPanel } from "@/components/file-detail-panel";
import { HotspotTable } from "@/components/hotspot-table";
import { MiniSparkline } from "@/components/charts/mini-sparkline";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { BranchMultiSelect } from "@/components/branch-multi-select";
import { SyncLogViewer, ViewLogsButton } from "@/components/sync-log-viewer";
import { api } from "@/lib/api-client";
import type { Repository, RepoStats, DailyStat, SyncJob, Branch, ContributorSummary, FileTreeNode } from "@/lib/types";

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  failed: <AlertCircle className="h-4 w-4 text-destructive" />,
  running: <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />,
  queued: <Clock className="h-4 w-4 text-muted-foreground" />,
  cancelled: <Ban className="h-4 w-4 text-amber-500" />,
};

export default function RepoDetailPage() {
  const { projectId, repoId } = useParams<{ projectId: string; repoId: string }>();
  const [repo, setRepo] = useState<Repository | null>(null);
  const [stats, setStats] = useState<RepoStats | null>(null);
  const [daily, setDaily] = useState<DailyStat[]>([]);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedBranches, setSelectedBranches] = useState<string[]>([]);
  const [contributors, setContributors] = useState<ContributorSummary[]>([]);
  const [contribSearch, setContribSearch] = useState("");
  const [contribSort, setContribSort] = useState<{ key: "name" | "email" | "lines"; dir: "asc" | "desc" }>({ key: "name", dir: "asc" });
  const [showInactive, setShowInactive] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [syncing, setSyncing] = useState(false);
  const [drillDown, setDrillDown] = useState<{ title: string; metric: string } | null>(null);
  const [fileTree, setFileTree] = useState<FileTreeNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [filesBranch, setFilesBranch] = useState<string | undefined>(undefined);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const pollTimer = useRef<NodeJS.Timeout | null>(null);

  const branchParam = selectedBranches.length > 0 ? selectedBranches : undefined;

  const refreshData = useCallback(async (branchFilter?: string[]) => {
    if (!repoId) return;
    const [s, d, c] = await Promise.all([
      api.getRepoStats(repoId, { branches: branchFilter, from_date: dateRange.from, to_date: dateRange.to }),
      api.dailyStats({ repository_id: repoId, branch: branchFilter, from_date: dateRange.from, to_date: dateRange.to }),
      api.listRepoContributors(repoId, branchFilter),
    ]);
    setStats(s);
    setDaily(d);
    setContributors(c);
  }, [repoId, dateRange]);

  const refreshAll = useCallback(async () => {
    if (!repoId) return;
    const [r, j, b, ft] = await Promise.all([
      api.getRepo(repoId),
      api.listSyncJobs(repoId),
      api.listBranches(repoId),
      api.getFileTree(repoId, filesBranch),
    ]);
    setRepo(r);
    setSyncJobs(j);
    setBranches(b);
    setFileTree(ft);
    await refreshData(selectedBranches.length > 0 ? selectedBranches : undefined);
  }, [repoId, refreshData, selectedBranches, filesBranch]);

  useEffect(() => {
    if (!repoId) return;
    Promise.all([
      api.getRepo(repoId),
      api.listSyncJobs(repoId),
      api.listBranches(repoId),
      api.getRepoStats(repoId, { from_date: dateRange.from, to_date: dateRange.to }),
      api.dailyStats({ repository_id: repoId, from_date: dateRange.from, to_date: dateRange.to }),
      api.listRepoContributors(repoId),
    ]).then(([r, j, b, s, d, c]) => {
      setRepo(r);
      setSyncJobs(j);
      setBranches(b);
      setStats(s);
      setDaily(d);
      setContributors(c);
      const defaultBr = r.default_branch || undefined;
      setFilesBranch(defaultBr);
      api.getFileTree(repoId, defaultBr).then(setFileTree);
    });
  }, [repoId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!repoId) return;
    refreshData(branchParam);
  }, [selectedBranches, dateRange]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!repoId || filesBranch === undefined) return;
    setSelectedFile(null);
    api.getFileTree(repoId, filesBranch).then(setFileTree);
  }, [repoId, filesBranch]);

  useEffect(() => {
    return () => { if (pollTimer.current) clearTimeout(pollTimer.current); };
  }, []);

  function stopPolling() {
    if (pollTimer.current) clearTimeout(pollTimer.current);
    pollTimer.current = null;
    setSyncing(false);
    setActiveJobId(null);
  }

  function pollSyncJob(jobId: string) {
    const check = async () => {
      if (!repoId) return;
      try {
        const jobs = await api.listSyncJobs(repoId);
        setSyncJobs(jobs);
        const job = jobs.find((j) => j.id === jobId);
        if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
          stopPolling();
          await refreshAll();
          return;
        }
      } catch { /* keep polling */ }
      pollTimer.current = setTimeout(check, 3000);
    };
    pollTimer.current = setTimeout(check, 3000);
  }

  async function handleSync() {
    if (!repoId || syncing) return;
    setSyncing(true);
    try {
      const job = await api.syncRepo(repoId);
      setActiveJobId(job.id);
      const jobs = await api.listSyncJobs(repoId);
      setSyncJobs(jobs);
      pollSyncJob(job.id);
    } catch {
      setSyncing(false);
    }
  }

  async function handleCancel() {
    if (!repoId || !activeJobId) return;
    try {
      await api.cancelSyncJob(repoId, activeJobId);
      stopPolling();
      await refreshAll();
    } catch { /* ignore */ }
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

  const contribStats = useMemo(() => {
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

  if (!repo) return <div className="animate-pulse text-muted-foreground">Loading repository...</div>;

  const hasActivity = (id: string) => {
    const cs = contribStats.get(id);
    return cs ? cs.added + cs.deleted > 0 : false;
  };

  const sortContribs = (list: ContributorSummary[]) =>
    list.sort((a, b) => {
      if (contribSort.key === "lines") {
        const aTotal = (contribStats.get(a.id)?.added || 0) + (contribStats.get(a.id)?.deleted || 0);
        const bTotal = (contribStats.get(b.id)?.added || 0) + (contribStats.get(b.id)?.deleted || 0);
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
          </div>
        </div>
        <div className="flex items-center gap-2">
          {syncing ? (
            <>
              <Button disabled>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Syncing...
              </Button>
              <Button variant="destructive" onClick={handleCancel}>
                <XCircle className="mr-2 h-4 w-4" /> Cancel
              </Button>
            </>
          ) : (
            <Button onClick={handleSync}>
              <RefreshCw className="mr-2 h-4 w-4" /> Sync Now
            </Button>
          )}
        </div>
      </div>

      {syncing && activeJobId && (
        <SyncLogViewer repoId={repoId} jobId={activeJobId} onDone={() => { stopPolling(); refreshAll(); }} />
      )}

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        {branches.length > 0 && (
          <BranchMultiSelect
            branches={branches}
            selected={selectedBranches}
            onChange={setSelectedBranches}
          />
        )}
        <div className="h-6 w-px bg-border" />
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      {stats && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard title="Total Commits" value={stats.total_commits} tooltip="Total number of commits in this repository for the selected period" onClick={() => setDrillDown({ title: "Total Commits", metric: "commits" })} />
            <StatCard title="Contributors" value={stats.contributor_count} tooltip="Number of unique people who made commits in the selected period" onClick={() => setDrillDown({ title: "Contributors", metric: "contributors" })} />
            <StatCard title="Bus Factor" value={stats.bus_factor} subtitle="50% commit threshold" tooltip="Minimum number of contributors whose combined work accounts for 50% of all commits. Low values mean knowledge is concentrated in few people — a risk if they leave." onClick={() => setDrillDown({ title: "Bus Factor", metric: "bus_factor" })} />
            <StatCard title="Commits/Day (7d)" value={stats.trends.avg_commits_7d} trend={stats.trends.wow_commits_delta} tooltip="Average number of commits per day over the last 7 days. The trend shows week-over-week change." onClick={() => setDrillDown({ title: "Commits/Day (7d)", metric: "commits_per_day" })} />
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard title="PR Cycle Time" value={`${stats.pr_cycle_time_hours}h`} subtitle="Avg open to merge" tooltip="Average time from when a pull request is opened to when it gets merged. Lower is better." />
            <StatCard title="Review Turnaround" value={`${stats.pr_review_turnaround_hours}h`} subtitle="Avg to first review" tooltip="Average time from when a pull request is opened until it receives its first code review. Lower means faster feedback." />
            <StatCard title="Churn Ratio" value={stats.churn_ratio} subtitle="Deleted / added lines" tooltip="Ratio of lines deleted to lines added. High churn can indicate rework, refactoring, or unstable code." onClick={() => setDrillDown({ title: "Churn Ratio", metric: "churn" })} />
            <StatCard title="Work Distribution" value={stats.contribution_gini} subtitle="Gini (0=even, 1=concentrated)" tooltip="Measures how evenly work is spread across contributors. 0 means everyone contributes equally, 1 means one person does all the work." onClick={() => setDrillDown({ title: "Work Distribution", metric: "work_distribution" })} />
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
              <Input
                placeholder="Filter by name or email..."
                value={contribSearch}
                onChange={(e) => setContribSearch(e.target.value)}
                className="pl-9"
              />
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
                  const cs = contribStats.get(c.id);
                  return (
                    <TableRow key={c.id}>
                      <TableCell>
                        <Link href={`/contributors/${c.id}`} className="flex items-center gap-2 font-medium hover:underline">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                            {c.canonical_name.charAt(0).toUpperCase()}
                          </div>
                          {c.canonical_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{c.canonical_email}</TableCell>
                      <TableCell className="text-xs whitespace-nowrap">
                        <span className="text-emerald-500">+{(cs?.added || 0).toLocaleString()}</span>
                        {" / "}
                        <span className="text-red-500">-{(cs?.deleted || 0).toLocaleString()}</span>
                      </TableCell>
                      <TableCell>
                        <div className="h-8 w-28">
                          <MiniSparkline data={cs!.sparkline} color="var(--chart-1)" />
                        </div>
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
                        <button
                          onClick={() => setShowInactive((v) => !v)}
                          className="flex w-full items-center gap-2 px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                          {showInactive ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                          {inactiveContribs.length} inactive contributor{inactiveContribs.length !== 1 ? "s" : ""}
                        </button>
                      </TableCell>
                    </TableRow>
                    {showInactive && inactiveContribs.map((c) => (
                      <TableRow key={c.id} className="text-muted-foreground">
                        <TableCell>
                          <Link href={`/contributors/${c.id}`} className="flex items-center gap-2 font-medium hover:underline">
                            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
                              {c.canonical_name.charAt(0).toUpperCase()}
                            </div>
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

      <Tabs defaultValue="files" className="space-y-4">
        <div className="flex items-center gap-3">
          <TabsList>
            <TabsTrigger value="files" className="gap-2"><FileCode2 className="h-4 w-4" /> Files</TabsTrigger>
            <TabsTrigger value="hotspots" className="gap-2"><Flame className="h-4 w-4" /> Hotspots</TabsTrigger>
          </TabsList>
          {branches.length > 0 && (
            <Select value={filesBranch ?? ""} onValueChange={(v) => setFilesBranch(v || undefined)}>
              <SelectTrigger className="w-48 h-9">
                <GitBranch className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
                <SelectValue placeholder="All branches" />
              </SelectTrigger>
              <SelectContent>
                {branches.map((b) => (
                  <SelectItem key={b.id} value={b.name}>{b.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

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
                  <TableCell className="flex items-center gap-2">
                    {STATUS_ICON[j.status] || null}
                    <span className="capitalize">{j.status}</span>
                  </TableCell>
                  <TableCell>{j.started_at ? new Date(j.started_at).toLocaleString() : "-"}</TableCell>
                  <TableCell>{j.finished_at ? new Date(j.finished_at).toLocaleString() : "-"}</TableCell>
                  <TableCell className="max-w-xs truncate text-destructive">{j.error_message || "-"}</TableCell>
                  <TableCell>
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
