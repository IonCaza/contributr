"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { GitBranch, Users, Plus, RefreshCw, Loader2, XCircle, ArrowUpDown, Search, ChevronDown, ChevronRight, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatCard } from "@/components/stat-card";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { MiniSparkline } from "@/components/charts/mini-sparkline";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { api } from "@/lib/api-client";
import type { ProjectDetail, ProjectStats, DailyStat, SSHKey, ContributorSummary } from "@/lib/types";

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([]);
  const [sshKeys, setSSHKeys] = useState<SSHKey[]>([]);
  const [open, setOpen] = useState(false);
  const [syncingRepos, setSyncingRepos] = useState<Map<string, string>>(new Map());
  const [contribSearch, setContribSearch] = useState("");
  const [contribSort, setContribSort] = useState<{ key: "name" | "email" | "lines"; dir: "asc" | "desc" }>({ key: "name", dir: "asc" });
  const [showInactive, setShowInactive] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [repoForm, setRepoForm] = useState({ name: "", ssh_url: "", platform: "github", platform_owner: "", platform_repo: "", ssh_credential_id: "" });
  const [editRepo, setEditRepo] = useState<{ id: string; name: string; ssh_url: string; platform: string; platform_owner: string; platform_repo: string; default_branch: string; ssh_credential_id: string } | null>(null);
  const [deleteRepoId, setDeleteRepoId] = useState<string | null>(null);
  const pollTimers = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Stable data: project detail + SSH keys
  useEffect(() => {
    if (!projectId) return;
    Promise.all([
      api.getProject(projectId),
      api.listSSHKeys(),
    ]).then(([p, k]) => {
      setProject(p);
      setSSHKeys(k);
    });
  }, [projectId]);

  // Filter-dependent data: stats + daily activity
  const refreshStats = useCallback(async () => {
    if (!projectId) return;
    const [s, d] = await Promise.all([
      api.getProjectStats(projectId, { from_date: dateRange.from, to_date: dateRange.to }),
      api.dailyStats({ project_id: projectId, from_date: dateRange.from, to_date: dateRange.to }),
    ]);
    setStats(s);
    setDailyStats(d);
  }, [projectId, dateRange]);

  useEffect(() => { refreshStats(); }, [refreshStats]);

  const refreshAll = useCallback(async () => {
    if (!projectId) return;
    const [p] = await Promise.all([
      api.getProject(projectId),
      refreshStats(),
    ]);
    setProject(p);
  }, [projectId, refreshStats]);

  useEffect(() => {
    return () => {
      pollTimers.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  function stopPolling(repoId: string) {
    const timer = pollTimers.current.get(repoId);
    if (timer) clearTimeout(timer);
    pollTimers.current.delete(repoId);
    setSyncingRepos((prev) => {
      const next = new Map(prev);
      next.delete(repoId);
      return next;
    });
  }

  function pollSyncJob(repoId: string, jobId: string) {
    const check = async () => {
      try {
        const jobs = await api.listSyncJobs(repoId);
        const job = jobs.find((j) => j.id === jobId);
        if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
          stopPolling(repoId);
          await refreshAll();
          return;
        }
      } catch { /* keep polling */ }
      const timer = setTimeout(check, 3000);
      pollTimers.current.set(repoId, timer);
    };
    const timer = setTimeout(check, 3000);
    pollTimers.current.set(repoId, timer);
  }

  async function handleSync(repoId: string) {
    if (syncingRepos.has(repoId)) return;
    try {
      const job = await api.syncRepo(repoId);
      setSyncingRepos((prev) => new Map(prev).set(repoId, job.id));
      pollSyncJob(repoId, job.id);
    } catch { /* ignore */ }
  }

  async function handleCancel(repoId: string) {
    const jobId = syncingRepos.get(repoId);
    if (!jobId) return;
    try {
      await api.cancelSyncJob(repoId, jobId);
      stopPolling(repoId);
      await refreshAll();
    } catch { /* ignore */ }
  }

  async function handleSyncAll() {
    if (!project) return;
    const toSync = project.repositories.filter((r) => !syncingRepos.has(r.id));
    for (const r of toSync) {
      try {
        const job = await api.syncRepo(r.id);
        setSyncingRepos((prev) => new Map(prev).set(r.id, job.id));
        pollSyncJob(r.id, job.id);
      } catch { /* ignore individual failures */ }
    }
  }

  async function handleAddRepo(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId) return;
    await api.createRepo(projectId, {
      ...repoForm,
      ssh_credential_id: repoForm.ssh_credential_id || null,
    });
    const p = await api.getProject(projectId);
    setProject(p);
    setOpen(false);
    setRepoForm({ name: "", ssh_url: "", platform: "github", platform_owner: "", platform_repo: "", ssh_credential_id: "" });
  }

  async function handleEditRepo(e: React.FormEvent) {
    e.preventDefault();
    if (!editRepo || !projectId) return;
    await api.updateRepo(editRepo.id, {
      name: editRepo.name,
      ssh_url: editRepo.ssh_url || null,
      platform: editRepo.platform,
      platform_owner: editRepo.platform_owner || null,
      platform_repo: editRepo.platform_repo || null,
      default_branch: editRepo.default_branch,
      ssh_credential_id: editRepo.ssh_credential_id || null,
    });
    setProject(await api.getProject(projectId));
    setEditRepo(null);
  }

  async function handleDeleteRepo() {
    if (!deleteRepoId || !projectId) return;
    try {
      await api.deleteRepo(deleteRepoId);
      setProject(await api.getProject(projectId));
    } catch { /* ignore */ }
    setDeleteRepoId(null);
  }

  const chartData = useMemo(() => dailyStats.map((d) => ({
    date: d.date.slice(5),
    lines_added: d.lines_added,
    lines_deleted: d.lines_deleted,
    commits: d.commits,
  })), [dailyStats]);

  const contribStats = useMemo(() => {
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

  if (!project) return <div className="animate-pulse text-muted-foreground">Loading project...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{project.name}</h1>
        {project.description && <p className="text-muted-foreground">{project.description}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      {stats && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard title="Repositories" value={stats.repository_count} />
          <StatCard title="Total Commits" value={stats.total_commits} />
          <StatCard title="Contributors" value={stats.contributor_count} />
          <StatCard title="Commits/Day (30d)" value={stats.trends.avg_commits_30d} trend={stats.trends.wow_commits_delta} />
        </div>
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
            <Button
              variant="outline"
              size="sm"
              onClick={handleSyncAll}
              disabled={project.repositories.every((r) => syncingRepos.has(r.id))}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${project.repositories.some((r) => syncingRepos.has(r.id)) ? "animate-spin" : ""}`} />
              Sync All
            </Button>
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
              <Button type="submit" className="w-full">Add Repository</Button>
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
              <TableHead>Repository</TableHead>
              <TableHead>Platform</TableHead>
              <TableHead>Last Synced</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {project.repositories.map((r) => {
              const isSyncing = syncingRepos.has(r.id);
              return (
                <TableRow key={r.id}>
                  <TableCell><GitBranch className="h-4 w-4 text-muted-foreground" /></TableCell>
                  <TableCell>
                    <Link href={`/projects/${projectId}/repositories/${r.id}`} className="font-medium hover:underline">
                      {r.name}
                    </Link>
                  </TableCell>
                  <TableCell><Badge variant="secondary" className="text-[10px]">{r.platform}</Badge></TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {isSyncing ? (
                      <span className="flex items-center gap-1 text-blue-500">
                        <Loader2 className="h-3 w-3 animate-spin" /> Syncing...
                      </span>
                    ) : r.last_synced_at ? (
                      new Date(r.last_synced_at).toLocaleDateString()
                    ) : (
                      "Never"
                    )}
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
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditRepo({
                          id: r.id,
                          name: r.name,
                          ssh_url: r.ssh_url || "",
                          platform: r.platform,
                          platform_owner: r.platform_owner || "",
                          platform_repo: r.platform_repo || "",
                          default_branch: r.default_branch,
                          ssh_credential_id: r.ssh_credential_id || "",
                        })}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteRepoId(r.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
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

      <AlertDialog open={!!deleteRepoId} onOpenChange={(v) => !v && setDeleteRepoId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Repository</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the repository and all associated data including commits, branches, sync history, and contributor statistics. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteRepo} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {project.contributors.length > 0 && (() => {
        const hasActivity = (id: string) => {
          const cs = contribStats.get(id);
          return cs ? cs.added + cs.deleted > 0 : false;
        };
        const sortFn = (a: ContributorSummary, b: ContributorSummary) => {
          if (contribSort.key === "lines") {
            const aTotal = (contribStats.get(a.id)?.added || 0) + (contribStats.get(a.id)?.deleted || 0);
            const bTotal = (contribStats.get(b.id)?.added || 0) + (contribStats.get(b.id)?.deleted || 0);
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
                      <button
                        className="flex items-center gap-1 hover:text-foreground"
                        onClick={() => setContribSort((s) => ({ key: "name", dir: s.key === "name" && s.dir === "asc" ? "desc" : "asc" }))}
                      >
                        Name <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button
                        className="flex items-center gap-1 hover:text-foreground"
                        onClick={() => setContribSort((s) => ({ key: "email", dir: s.key === "email" && s.dir === "asc" ? "desc" : "asc" }))}
                      >
                        Email <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button
                        className="flex items-center gap-1 hover:text-foreground"
                        onClick={() => setContribSort((s) => ({ key: "lines", dir: s.key === "lines" && s.dir === "desc" ? "asc" : "desc" }))}
                      >
                        +/- Lines <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </TableHead>
                    <TableHead className="w-32">Activity (30d)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {active.map((c) => {
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
                          <button
                            onClick={() => setShowInactive((v) => !v)}
                            className="flex w-full items-center gap-2 px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                          >
                            {showInactive ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                            {inactive.length} inactive contributor{inactive.length !== 1 ? "s" : ""}
                          </button>
                        </TableCell>
                      </TableRow>
                      {showInactive && inactive.map((c) => (
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
        );
      })()}
    </div>
  );
}
