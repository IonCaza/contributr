"use client";

import React, { use, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { GitBranch, Plus, RefreshCw, Loader2, XCircle, ArrowUpDown, Search, ChevronDown, ChevronRight, Pencil, Trash2, Eraser, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatCard } from "@/components/stat-card";
import { FilterBarSkeleton, StatRowSkeleton, ChartSkeleton, TableSkeleton } from "@/components/page-skeleton";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { StatDetailSheet } from "@/components/stat-detail-sheet";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { MiniSparkline } from "@/components/charts/mini-sparkline";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import type { ContributorSummary } from "@/lib/types";
import { CodeSubTabs } from "@/components/code-sub-tabs";
import { useProject, useProjectStats } from "@/hooks/use-projects";
import { useSSHKeys } from "@/hooks/use-settings";
import { useCreateRepo, useDeleteRepo, usePurgeRepo, useSyncRepo } from "@/hooks/use-repos";
import { useDailyStats } from "@/hooks/use-daily-stats";
import { useIterations } from "@/hooks/use-delivery";

export default function ProjectCodePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const qc = useQueryClient();
  const { data: project } = useProject(projectId);
  const { data: sshKeys = [] } = useSSHKeys();

  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [sprintAlign, setSprintAlign] = useState<string>("");

  const { data: iterations = [] } = useIterations(projectId);
  const { data: stats } = useProjectStats(projectId, { from: dateRange.from, to: dateRange.to });

  const sortedIterations = useMemo(() => {
    const now = new Date();
    return (iterations || [])
      .map((it) => {
        const start = it.start_date ? new Date(it.start_date) : null;
        const end = it.end_date ? new Date(it.end_date) : null;
        let status: "active" | "upcoming" | "past" = "past";
        if (start && end) {
          if (start <= now && end >= now) status = "active";
          else if (start > now) status = "upcoming";
        }
        return { ...it, _status: status };
      })
      .sort((a, b) => {
        const aStart = a.start_date ? new Date(a.start_date).getTime() : 0;
        const bStart = b.start_date ? new Date(b.start_date).getTime() : 0;
        return aStart - bStart;
      });
  }, [iterations]);

  const handleSprintAlign = useCallback(
    (val: string) => {
      setSprintAlign(val);
      if (val === "__none__") {
        setDateRange(defaultRange());
        return;
      }
      const it = (iterations || []).find((i) => i.id === val);
      if (it?.start_date && it?.end_date) {
        setDateRange({ from: it.start_date, to: it.end_date });
      }
    },
    [iterations],
  );

  const dailyParams = useMemo(() => ({
    project_id: projectId,
    from_date: dateRange.from,
    to_date: dateRange.to,
  }), [projectId, dateRange]);
  const { data: dailyStats = [] } = useDailyStats(dailyParams);

  const createRepo = useCreateRepo(projectId);
  const deleteRepo = useDeleteRepo(projectId);
  const purgeRepo = usePurgeRepo(projectId);
  const syncRepo = useSyncRepo();

  const [open, setOpen] = useState(false);
  const [syncingRepos, setSyncingRepos] = useState<Map<string, string>>(new Map());
  const [scanningRepos, setScanningRepos] = useState<Map<string, { runId: string; repoId: string }>>(new Map());
  const [contribSearch, setContribSearch] = useState("");
  const [contribSort, setContribSort] = useState<{ key: "name" | "email" | "lines"; dir: "asc" | "desc" }>({ key: "name", dir: "asc" });
  const [repoSort, setRepoSort] = useState<{ key: "name" | "platform" | "last_synced"; dir: "asc" | "desc" }>({ key: "name", dir: "asc" });
  const [showInactive, setShowInactive] = useState(false);
  const [drillDown, setDrillDown] = useState<{ title: string; metric: string } | null>(null);
  const [repoForm, setRepoForm] = useState({ name: "", ssh_url: "", platform: "github", platform_owner: "", platform_repo: "", ssh_credential_id: "" });
  const [editRepo, setEditRepo] = useState<{ id: string; name: string; ssh_url: string; platform: string; platform_owner: string; platform_repo: string; default_branch: string; ssh_credential_id: string } | null>(null);
  const [deleteRepoId, setDeleteRepoId] = useState<string | null>(null);
  const [purgeRepoId, setPurgeRepoId] = useState<string | null>(null);
  const [purgeAllOpen, setPurgeAllOpen] = useState(false);
  const [purging, setPurging] = useState<Set<string>>(new Set());

  function invalidateAll() {
    qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    qc.invalidateQueries({ queryKey: queryKeys.projects.stats(projectId) });
    qc.invalidateQueries({ queryKey: queryKeys.daily(dailyParams) });
  }

  function stopPolling(repoId: string) {
    setSyncingRepos((prev) => {
      const next = new Map(prev);
      next.delete(repoId);
      return next;
    });
  }

  async function handleSync(repoId: string) {
    if (syncingRepos.has(repoId)) return;
    try {
      const job = await syncRepo.mutateAsync(repoId);
      setSyncingRepos((prev) => new Map(prev).set(repoId, job.id));
    } catch { /* ignore */ }
  }

  async function handleCancel(repoId: string) {
    const jobId = syncingRepos.get(repoId);
    if (!jobId) return;
    try {
      await api.cancelSyncJob(repoId, jobId);
      stopPolling(repoId);
      invalidateAll();
    } catch { /* ignore */ }
  }

  async function handleSyncAll() {
    if (!project) return;
    const toSync = project.repositories.filter((r) => !syncingRepos.has(r.id));
    for (const r of toSync) {
      try {
        const job = await syncRepo.mutateAsync(r.id);
        setSyncingRepos((prev) => new Map(prev).set(r.id, job.id));
      } catch { /* ignore individual failures */ }
    }
  }

  async function handleScan(repoId: string) {
    if (scanningRepos.has(repoId)) return;
    try {
      const run = await api.triggerSastScan(repoId);
      setScanningRepos((prev) => new Map(prev).set(repoId, { runId: run.id, repoId }));
    } catch { /* ignore */ }
  }

  function stopScanPolling(repoId: string) {
    setScanningRepos((prev) => {
      const next = new Map(prev);
      next.delete(repoId);
      return next;
    });
  }

  async function handleAddRepo(e: React.FormEvent) {
    e.preventDefault();
    await createRepo.mutateAsync({ ...repoForm, ssh_credential_id: repoForm.ssh_credential_id || null });
    setOpen(false);
    setRepoForm({ name: "", ssh_url: "", platform: "github", platform_owner: "", platform_repo: "", ssh_credential_id: "" });
  }

  async function handleEditRepo(e: React.FormEvent) {
    e.preventDefault();
    if (!editRepo) return;
    await api.updateRepo(editRepo.id, {
      name: editRepo.name,
      ssh_url: editRepo.ssh_url || null,
      platform: editRepo.platform,
      platform_owner: editRepo.platform_owner || null,
      platform_repo: editRepo.platform_repo || null,
      default_branch: editRepo.default_branch,
      ssh_credential_id: editRepo.ssh_credential_id || null,
    });
    qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    setEditRepo(null);
  }

  async function handleDeleteRepo() {
    if (!deleteRepoId) return;
    await deleteRepo.mutateAsync(deleteRepoId);
    setDeleteRepoId(null);
  }

  async function handlePurgeRepo() {
    if (!purgeRepoId) return;
    setPurging((prev) => new Set(prev).add(purgeRepoId));
    try {
      await purgeRepo.mutateAsync(purgeRepoId);
    } catch { /* ignore */ }
    setPurging((prev) => { const next = new Set(prev); next.delete(purgeRepoId); return next; });
    setPurgeRepoId(null);
  }

  async function handlePurgeAll() {
    if (!project) return;
    const ids = project.repositories.map((r) => r.id);
    setPurging(new Set(ids));
    setPurgeAllOpen(false);
    try {
      await Promise.all(ids.map((id) => purgeRepo.mutateAsync(id)));
    } catch { /* ignore */ }
    setPurging(new Set());
  }

  const chartData = useMemo(() => dailyStats.map((d) => ({
    date: d.date.slice(5),
    lines_added: d.lines_added,
    lines_deleted: d.lines_deleted,
    commits: d.commits,
  })), [dailyStats]);

  const contribStatsMap = useMemo(() => {
    const map = new Map<string, { added: number; deleted: number; sparkline: number[] }>();
    const byContribDate = new Map<string, Map<string, number>>();
    dailyStats.forEach((d) => {
      const existing = map.get(d.contributor_id) || { added: 0, deleted: 0, sparkline: [] };
      existing.added += d.lines_added;
      existing.deleted += d.lines_deleted;
      map.set(d.contributor_id, existing);
      if (!byContribDate.has(d.contributor_id)) byContribDate.set(d.contributor_id, new Map());
      const dateMap = byContribDate.get(d.contributor_id)!;
      const dateKey = d.date.slice(0, 10);
      dateMap.set(dateKey, (dateMap.get(dateKey) || 0) + d.lines_added + d.lines_deleted);
    });
    const allDates = [...new Set(dailyStats.map((d) => d.date.slice(0, 10)))].sort();
    const recentDates = allDates.slice(-30);
    for (const [cid, entry] of map) {
      const dateMap = byContribDate.get(cid) || new Map();
      entry.sparkline = recentDates.map((d) => dateMap.get(d) || 0);
    }
    return map;
  }, [dailyStats]);

  const sortedRepos = useMemo(() => {
    if (!project) return [];
    return [...project.repositories].sort((a, b) => {
      let cmp = 0;
      if (repoSort.key === "name") cmp = a.name.localeCompare(b.name);
      else if (repoSort.key === "platform") cmp = a.platform.localeCompare(b.platform);
      else if (repoSort.key === "last_synced") {
        const aTime = a.last_synced_at ? new Date(a.last_synced_at).getTime() : 0;
        const bTime = b.last_synced_at ? new Date(b.last_synced_at).getTime() : 0;
        cmp = aTime - bTime;
      }
      return repoSort.dir === "asc" ? cmp : -cmp;
    });
  }, [project, repoSort]);

  if (!project) return (
    <div className="space-y-6">
      <FilterBarSkeleton />
      <StatRowSkeleton />
      <StatRowSkeleton />
      <ChartSkeleton />
      <TableSkeleton rows={4} cols={5} />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        {sortedIterations.length > 0 && (
          <Select value={sprintAlign} onValueChange={handleSprintAlign}>
            <SelectTrigger className="w-72">
              <SelectValue placeholder="Align to Sprint" />
            </SelectTrigger>
            <SelectContent className="max-h-80">
              <SelectItem value="__none__">
                <span className="text-muted-foreground">No Sprint Alignment</span>
              </SelectItem>
              {sortedIterations.map((it) => {
                const s = it.stats;
                const pct = s && s.total_items > 0 ? Math.round((s.completed_items / s.total_items) * 100) : null;
                return (
                  <SelectItem key={it.id} value={it.id}>
                    <span className="flex items-center gap-2">
                      <Badge
                        variant="secondary"
                        className={cn(
                          "text-[9px] px-1.5 py-0 leading-4 shrink-0",
                          it._status === "active" && "bg-green-500/15 text-green-700 dark:text-green-400",
                          it._status === "upcoming" && "bg-blue-500/15 text-blue-700 dark:text-blue-400",
                          it._status === "past" && "bg-muted text-muted-foreground",
                        )}
                      >
                        {it._status === "active" ? "Active" : it._status === "upcoming" ? "Future" : "Past"}
                      </Badge>
                      <span className="truncate">{it.name}</span>
                      <span className="ml-auto shrink-0 text-[11px] text-muted-foreground tabular-nums">
                        {it.start_date && it.end_date
                          ? `${it.start_date} → ${it.end_date}`
                          : "No dates"}
                        {pct !== null && ` · ${pct}%`}
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        )}

        {sortedIterations.length > 0 && <div className="h-5 w-px bg-border" />}

        <DateRangeFilter value={dateRange} onChange={setDateRange} />

        {sprintAlign && sprintAlign !== "__none__" && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-7"
            onClick={() => {
              setSprintAlign("");
              setDateRange(defaultRange());
            }}
          >
            Reset
          </Button>
        )}
      </div>

      <CodeSubTabs projectId={projectId} />

      {stats && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard className={ANIM_CARD} style={stagger(0)} title="Repositories" value={stats.repository_count} tooltip="Number of repositories tracked in this project" />
            <StatCard className={ANIM_CARD} style={stagger(1)} title="Total Commits" value={stats.total_commits} tooltip="Total number of commits across all repositories in the selected period" onClick={() => setDrillDown({ title: "Total Commits", metric: "commits" })} />
            <StatCard className={ANIM_CARD} style={stagger(2)} title="Contributors" value={stats.contributor_count} tooltip="Number of unique people who made commits in the selected period" onClick={() => setDrillDown({ title: "Contributors", metric: "contributors" })} />
            <StatCard className={ANIM_CARD} style={stagger(3)} title="Commits/Day (30d)" value={stats.trends.avg_commits_30d} trend={stats.trends.wow_commits_delta} tooltip="Average number of commits per day over the last 30 days. The trend shows week-over-week change." onClick={() => setDrillDown({ title: "Commits/Day (30d)", metric: "commits_per_day" })} />
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard className={ANIM_CARD} style={stagger(4)} title="PR Cycle Time" value={`${stats.pr_cycle_time_hours}h`} subtitle="Avg open to merge" tooltip="Average time from when a pull request is opened to when it gets merged. Lower is better." />
            <StatCard className={ANIM_CARD} style={stagger(5)} title="Review Turnaround" value={`${stats.pr_review_turnaround_hours}h`} subtitle="Avg to first review" tooltip="Average time from when a pull request is opened until it receives its first code review. Lower means faster feedback." />
            <StatCard className={ANIM_CARD} style={stagger(6)} title="Churn Ratio" value={stats.churn_ratio} subtitle="Deleted / added lines" tooltip="Ratio of lines deleted to lines added. High churn can indicate rework, refactoring, or unstable code." onClick={() => setDrillDown({ title: "Churn Ratio", metric: "churn" })} />
            <StatCard className={ANIM_CARD} style={stagger(7)} title="Work Distribution" value={stats.contribution_gini} subtitle="Gini (0=even, 1=concentrated)" tooltip="Measures how evenly work is spread across contributors. 0 means everyone contributes equally, 1 means one person does all the work." onClick={() => setDrillDown({ title: "Work Distribution", metric: "work_distribution" })} />
          </div>

          <StatDetailSheet
            open={!!drillDown}
            onOpenChange={(v) => { if (!v) setDrillDown(null); }}
            title={drillDown?.title ?? ""}
            metric={drillDown?.metric ?? "commits"}
            daily={dailyStats}
            contributorNames={Object.fromEntries(project.contributors.map((c) => [c.id, c.canonical_name]))}
            repoNames={Object.fromEntries(project.repositories.map((r) => [r.id, r.name]))}
          />
        </>
      )}

      {chartData.length > 0 ? (
        <ContributionAreaChart data={chartData} title="Activity" />
      ) : (
        <p className="text-sm text-muted-foreground">No activity data for this period.</p>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Repositories</h2>
        <div className="flex items-center gap-2">
          {project.repositories.length > 0 && (
            <>
              <Button variant="outline" size="sm" onClick={() => setPurgeAllOpen(true)} disabled={purging.size > 0}>
                <Eraser className={`mr-2 h-4 w-4 ${purging.size > 0 ? "animate-pulse" : ""}`} /> Purge All Data
              </Button>
              <Button variant="outline" size="sm" onClick={handleSyncAll} disabled={project.repositories.every((r) => syncingRepos.has(r.id))}>
                <RefreshCw className={`mr-2 h-4 w-4 ${project.repositories.some((r) => syncingRepos.has(r.id)) ? "animate-spin" : ""}`} /> Sync All
              </Button>
            </>
          )}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm"><Plus className="mr-2 h-4 w-4" /> Add Repository</Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle>Add Repository</DialogTitle></DialogHeader>
              <form onSubmit={handleAddRepo} className="space-y-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input value={repoForm.name} onChange={(e) => setRepoForm((f) => ({ ...f, name: e.target.value }))} required />
                </div>
                <div className="space-y-2">
                  <Label>SSH URL</Label>
                  <Input value={repoForm.ssh_url} onChange={(e) => setRepoForm((f) => ({ ...f, ssh_url: e.target.value }))} placeholder="git@github.com:org/repo.git" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Platform</Label>
                    <Select value={repoForm.platform} onValueChange={(v) => setRepoForm((f) => ({ ...f, platform: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="github">GitHub</SelectItem>
                        <SelectItem value="gitlab">GitLab</SelectItem>
                        <SelectItem value="azure">Azure DevOps</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>SSH Key</Label>
                    <Select value={repoForm.ssh_credential_id} onValueChange={(v) => setRepoForm((f) => ({ ...f, ssh_credential_id: v }))}>
                      <SelectTrigger><SelectValue placeholder="Select key" /></SelectTrigger>
                      <SelectContent>
                        {sshKeys.map((k) => (
                          <SelectItem key={k.id} value={k.id}>{k.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Owner / Org</Label>
                    <Input value={repoForm.platform_owner} onChange={(e) => setRepoForm((f) => ({ ...f, platform_owner: e.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Repo Name</Label>
                    <Input value={repoForm.platform_repo} onChange={(e) => setRepoForm((f) => ({ ...f, platform_repo: e.target.value }))} />
                  </div>
                </div>
                <Button type="submit" className="w-full" disabled={createRepo.isPending}>
                  {createRepo.isPending ? "Adding..." : "Add Repository"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8"></TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-foreground" onClick={() => setRepoSort((s) => ({ key: "name", dir: s.key === "name" && s.dir === "asc" ? "desc" : "asc" }))}>
                  Repository <ArrowUpDown className="h-3 w-3" />
                </button>
              </TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-foreground" onClick={() => setRepoSort((s) => ({ key: "platform", dir: s.key === "platform" && s.dir === "asc" ? "desc" : "asc" }))}>
                  Platform <ArrowUpDown className="h-3 w-3" />
                </button>
              </TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-foreground" onClick={() => setRepoSort((s) => ({ key: "last_synced", dir: s.key === "last_synced" && s.dir === "asc" ? "desc" : "asc" }))}>
                  Last Synced <ArrowUpDown className="h-3 w-3" />
                </button>
              </TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRepos.map((r) => {
              const isSyncing = syncingRepos.has(r.id);
              const syncJobId = syncingRepos.get(r.id);
              const isScanning = scanningRepos.has(r.id);
              const scanInfo = scanningRepos.get(r.id);
              return (
                <React.Fragment key={r.id}>
                  <TableRow>
                    <TableCell><GitBranch className="h-4 w-4 text-muted-foreground" /></TableCell>
                    <TableCell>
                      <Link href={`/projects/${projectId}/repositories/${r.id}`} className="font-medium hover:underline">{r.name}</Link>
                    </TableCell>
                    <TableCell><Badge variant="secondary" className="text-[10px]">{r.platform}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {isSyncing ? (
                        <span className="flex items-center gap-1 text-blue-500"><Loader2 className="h-3 w-3 animate-spin" /> Syncing...</span>
                      ) : r.last_synced_at ? new Date(r.last_synced_at).toLocaleDateString() : "Never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {isSyncing ? (
                          <Button variant="destructive" size="sm" onClick={() => handleCancel(r.id)}>
                            <XCircle className="mr-1 h-3 w-3" /> Cancel
                          </Button>
                        ) : (
                          <Button variant="outline" size="sm" onClick={() => handleSync(r.id)}>
                            <RefreshCw className="mr-1 h-3 w-3" /> Sync
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleScan(r.id)}
                          disabled={isScanning || isSyncing}
                        >
                          {isScanning ? (
                            <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> Scanning</>
                          ) : (
                            <><ShieldAlert className="mr-1 h-3 w-3" /> Scan</>
                          )}
                        </Button>
                        <Button variant="ghost" size="sm" className="text-amber-600 hover:text-amber-700" disabled={purging.has(r.id) || isSyncing} onClick={() => setPurgeRepoId(r.id)}>
                          <Eraser className={`h-3.5 w-3.5 ${purging.has(r.id) ? "animate-pulse" : ""}`} />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditRepo({ id: r.id, name: r.name, ssh_url: r.ssh_url || "", platform: r.platform, platform_owner: r.platform_owner || "", platform_repo: r.platform_repo || "", default_branch: r.default_branch, ssh_credential_id: r.ssh_credential_id || "" })}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteRepoId(r.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  {isSyncing && syncJobId && (
                    <TableRow>
                      <TableCell colSpan={5} className="p-2">
                        <SyncLogViewer
                          repoId={r.id}
                          jobId={syncJobId}
                          compact
                          onDone={() => { stopPolling(r.id); invalidateAll(); }}
                        />
                      </TableCell>
                    </TableRow>
                  )}
                  {isScanning && scanInfo && (
                    <TableRow>
                      <TableCell colSpan={5} className="p-2">
                        <SyncLogViewer
                          logUrl={`${api.getApiBase()}/repositories/${r.id}/sast/runs/${scanInfo.runId}/logs`}
                          compact
                          title="SAST Scan"
                          onDone={() => { stopScanPolling(r.id); invalidateAll(); }}
                        />
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={!!editRepo} onOpenChange={(v) => !v && setEditRepo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Repository</DialogTitle>
            <DialogDescription>Update repository details.</DialogDescription>
          </DialogHeader>
          {editRepo && (
            <form onSubmit={handleEditRepo} className="space-y-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={editRepo.name} onChange={(e) => setEditRepo({ ...editRepo, name: e.target.value })} required />
              </div>
              <div className="space-y-2">
                <Label>SSH URL</Label>
                <Input value={editRepo.ssh_url} onChange={(e) => setEditRepo({ ...editRepo, ssh_url: e.target.value })} placeholder="git@github.com:org/repo.git" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Platform</Label>
                  <Select value={editRepo.platform} onValueChange={(v) => setEditRepo({ ...editRepo, platform: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="github">GitHub</SelectItem>
                      <SelectItem value="gitlab">GitLab</SelectItem>
                      <SelectItem value="azure">Azure DevOps</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>SSH Key</Label>
                  <Select value={editRepo.ssh_credential_id} onValueChange={(v) => setEditRepo({ ...editRepo, ssh_credential_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Select key" /></SelectTrigger>
                    <SelectContent>
                      {sshKeys.map((k) => (
                        <SelectItem key={k.id} value={k.id}>{k.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Owner / Org</Label>
                  <Input value={editRepo.platform_owner} onChange={(e) => setEditRepo({ ...editRepo, platform_owner: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Repo Name</Label>
                  <Input value={editRepo.platform_repo} onChange={(e) => setEditRepo({ ...editRepo, platform_repo: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Default Branch</Label>
                  <Input value={editRepo.default_branch} onChange={(e) => setEditRepo({ ...editRepo, default_branch: e.target.value })} />
                </div>
              </div>
              <Button type="submit" className="w-full">Save Changes</Button>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteRepoId}
        onOpenChange={(v) => !v && setDeleteRepoId(null)}
        title="Delete Repository"
        description={<>This will permanently delete the repository <span className="font-semibold">{project.repositories.find((r) => r.id === deleteRepoId)?.name}</span> and all associated data including commits, branches, sync history, and contributor statistics. This action cannot be undone.</>}
        confirmLabel="Delete"
        expectedName={project.repositories.find((r) => r.id === deleteRepoId)?.name}
        expectedNameLabel="Type the repository name to confirm"
        onConfirm={handleDeleteRepo}
      />

      <AlertDialog open={!!purgeRepoId} onOpenChange={(v) => !v && setPurgeRepoId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Purge Repository Data</AlertDialogTitle>
            <AlertDialogDescription>
              This will delete all synced data for <span className="font-semibold">{project.repositories.find((r) => r.id === purgeRepoId)?.name}</span> — including commits, branches, file history, sync jobs, and statistics. The repository configuration will be kept so you can re-sync later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePurgeRepo} className="bg-amber-600 text-white hover:bg-amber-700">Purge Data</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={purgeAllOpen} onOpenChange={setPurgeAllOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Purge All Repository Data</AlertDialogTitle>
            <AlertDialogDescription>
              This will delete all synced data across <span className="font-semibold">all {project.repositories.length} repositories</span> in this project — including commits, branches, file history, sync jobs, and statistics. Repository configurations will be kept so you can re-sync later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePurgeAll} className="bg-amber-600 text-white hover:bg-amber-700">Purge All Data</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {project.contributors.length > 0 && (() => {
        const hasActivity = (id: string) => {
          const cs = contribStatsMap.get(id);
          return cs ? cs.added + cs.deleted > 0 : false;
        };
        const sortFn = (a: ContributorSummary, b: ContributorSummary) => {
          if (contribSort.key === "lines") {
            const aTotal = (contribStatsMap.get(a.id)?.added || 0) + (contribStatsMap.get(a.id)?.deleted || 0);
            const bTotal = (contribStatsMap.get(b.id)?.added || 0) + (contribStatsMap.get(b.id)?.deleted || 0);
            return contribSort.dir === "asc" ? aTotal - bTotal : bTotal - aTotal;
          }
          const valA = contribSort.key === "name" ? a.canonical_name : a.canonical_email;
          const valB = contribSort.key === "name" ? b.canonical_name : b.canonical_email;
          const cmp = valA.localeCompare(valB);
          return contribSort.dir === "asc" ? cmp : -cmp;
        };
        const filtered = project.contributors.filter((c) => {
          if (!contribSearch) return true;
          const q = contribSearch.toLowerCase();
          return c.canonical_name.toLowerCase().includes(q) || c.canonical_email.toLowerCase().includes(q);
        });
        const active = filtered.filter((c) => hasActivity(c.id)).sort(sortFn);
        const inactive = filtered.filter((c) => !hasActivity(c.id)).sort(sortFn);

        return (
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
                  {active.map((c) => {
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
                  {active.length === 0 && inactive.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="py-6 text-center text-muted-foreground">
                        {contribSearch ? `No contributors match \u201c${contribSearch}\u201d` : "No contributors found"}
                      </TableCell>
                    </TableRow>
                  )}
                  {inactive.length > 0 && (
                    <>
                      <TableRow>
                        <TableCell colSpan={4} className="p-0">
                          <button onClick={() => setShowInactive((v) => !v)} className="flex w-full items-center gap-2 px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                            {showInactive ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                            {inactive.length} inactive contributor{inactive.length !== 1 ? "s" : ""}
                          </button>
                        </TableCell>
                      </TableRow>
                      {showInactive && inactive.map((c) => (
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
        );
      })()}
    </div>
  );
}
