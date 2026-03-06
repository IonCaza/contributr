"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { RefreshCw, ExternalLink, ChevronLeft, ChevronRight, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatCard } from "@/components/stat-card";
import { ViewLogsButton } from "@/components/sync-log-viewer";
import { api } from "@/lib/api-client";
import { useDeliveryStats, useWorkItems, useIterations, useTriggerDeliverySync, useDeliverySyncJobs } from "@/hooks/use-delivery";

const TYPE_COLORS: Record<string, string> = {
  epic: "bg-purple-500/10 text-purple-700 dark:text-purple-400",
  feature: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
  user_story: "bg-green-500/10 text-green-700 dark:text-green-400",
  task: "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
  bug: "bg-red-500/10 text-red-700 dark:text-red-400",
};

const TYPE_LABELS: Record<string, string> = {
  epic: "Epic",
  feature: "Feature",
  user_story: "User Story",
  task: "Task",
  bug: "Bug",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  failed: <AlertCircle className="h-4 w-4 text-destructive" />,
  running: <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />,
  queued: <Clock className="h-4 w-4 text-muted-foreground" />,
  cancelled: <AlertCircle className="h-4 w-4 text-yellow-500" />,
};

function StateTag({ state }: { state: string }) {
  const lower = state.toLowerCase();
  let cls = "bg-muted text-muted-foreground";
  if (lower.includes("active") || lower.includes("progress")) cls = "bg-blue-500/10 text-blue-700 dark:text-blue-400";
  else if (lower.includes("resolved") || lower.includes("done") || lower.includes("completed")) cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed")) cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new")) cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return <Badge variant="secondary" className={`text-[10px] ${cls}`}>{state}</Badge>;
}

export function ProjectDeliveryTab({ projectId }: { projectId: string }) {
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [stateFilter, setStateFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const [syncing, setSyncing] = useState(false);
  const pageSize = 25;
  const qc = useQueryClient();

  const { data: stats, isLoading: statsLoading } = useDeliveryStats(projectId);
  const { data: iterations } = useIterations(projectId);
  const { data: workItemsData, isLoading: wiLoading } = useWorkItems(projectId, {
    work_item_type: typeFilter || undefined,
    state: stateFilter || undefined,
    page,
    page_size: pageSize,
  });
  const { data: syncJobs = [] } = useDeliverySyncJobs(projectId, syncing);
  const syncMutation = useTriggerDeliverySync(projectId);

  useEffect(() => {
    if (!syncing) return;
    const active = syncJobs.find((j) => j.status === "queued" || j.status === "running");
    if (!active && syncJobs.length > 0) {
      setSyncing(false);
      qc.invalidateQueries({ queryKey: ["delivery", projectId] });
    }
  }, [syncJobs, syncing, qc, projectId]);

  const handleSync = useCallback(() => {
    syncMutation.mutate(undefined, {
      onSuccess: () => setSyncing(true),
    });
  }, [syncMutation]);

  const activeIterations = useMemo(
    () => (iterations || []).filter((it) => {
      if (!it.start_date || !it.end_date) return false;
      const now = new Date();
      return new Date(it.start_date) <= now && new Date(it.end_date) >= now;
    }),
    [iterations],
  );

  const totalPages = workItemsData ? Math.ceil(workItemsData.total / pageSize) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Delivery Analytics</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSync}
          disabled={syncMutation.isPending || syncing}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${(syncMutation.isPending || syncing) ? "animate-spin" : ""}`} />
          {syncing ? "Syncing..." : "Sync from Azure DevOps"}
        </Button>
      </div>

      {statsLoading && <p className="text-muted-foreground animate-pulse">Loading delivery stats...</p>}

      {stats && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard title="Total Work Items" value={stats.total_work_items} tooltip="Total work items tracked in this project" />
            <StatCard title="Open Items" value={stats.open_items} tooltip="Work items in an active/new state" />
            <StatCard title="Completed" value={stats.completed_items} tooltip="Work items resolved or closed" />
            <StatCard
              title="Story Points Completed"
              value={stats.completed_story_points}
              subtitle={`of ${stats.total_story_points} total`}
              tooltip="Sum of story points on resolved/closed items"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard title="Avg Cycle Time" value={`${stats.avg_cycle_time_hours}h`} subtitle="Activated → Resolved" tooltip="Median hours from when a work item becomes active to resolved" />
            <StatCard title="Avg Lead Time" value={`${stats.avg_lead_time_hours}h`} subtitle="Created → Closed" tooltip="Median hours from creation to closure" />
            <StatCard title="Backlog Types" value={stats.backlog_by_type.length} subtitle="Distinct types" tooltip="Number of different work item types in the backlog" />
            <StatCard title="State Groups" value={stats.backlog_by_state.length} subtitle="Distinct states" tooltip="Number of distinct workflow states in use" />
          </div>

          {stats.velocity_trend.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Velocity (Story Points per Sprint)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-2 h-40">
                  {stats.velocity_trend.map((v, i) => {
                    const max = Math.max(...stats.velocity_trend.map((x) => x.points), 1);
                    const pct = (v.points / max) * 100;
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <span className="text-xs font-medium">{v.points}</span>
                        <div
                          className="w-full rounded-t bg-primary/70 transition-all"
                          style={{ height: `${pct}%`, minHeight: v.points > 0 ? 4 : 0 }}
                        />
                        <span className="text-[9px] text-muted-foreground truncate w-full text-center" title={v.iteration}>
                          {v.iteration.length > 10 ? v.iteration.slice(-10) : v.iteration}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {stats.throughput_trend.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Throughput (Created vs Completed)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-px h-32">
                  {stats.throughput_trend.slice(-60).map((t, i) => {
                    const max = Math.max(
                      ...stats.throughput_trend.slice(-60).map((x) => Math.max(x.created, x.completed)),
                      1,
                    );
                    return (
                      <div key={i} className="flex-1 flex gap-px items-end h-full" title={`${t.date}: ${t.created} created, ${t.completed} completed`}>
                        <div className="flex-1 bg-amber-400/60 rounded-t" style={{ height: `${(t.created / max) * 100}%`, minHeight: t.created > 0 ? 2 : 0 }} />
                        <div className="flex-1 bg-emerald-500/60 rounded-t" style={{ height: `${(t.completed / max) * 100}%`, minHeight: t.completed > 0 ? 2 : 0 }} />
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded bg-amber-400/60" /> Created</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded bg-emerald-500/60" /> Completed</span>
                </div>
              </CardContent>
            </Card>
          )}

          {(stats.backlog_by_type.length > 0 || stats.backlog_by_state.length > 0) && (
            <div className="grid gap-4 md:grid-cols-2">
              {stats.backlog_by_type.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Backlog by Type</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {stats.backlog_by_type.map((b) => (
                        <div key={b.type} className="flex items-center justify-between">
                          <Badge variant="secondary" className={TYPE_COLORS[b.type] || ""}>{TYPE_LABELS[b.type] || b.type}</Badge>
                          <span className="text-sm font-medium">{b.count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              {stats.backlog_by_state.length > 0 && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Backlog by State</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {stats.backlog_by_state.map((b) => (
                        <div key={b.state} className="flex items-center justify-between">
                          <StateTag state={b.state} />
                          <span className="text-sm font-medium">{b.count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </>
      )}

      {activeIterations.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Active Iterations</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sprint</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Points</TableHead>
                  <TableHead className="text-right">Progress</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeIterations.map((it) => {
                  const s = it.stats;
                  const pct = s && s.total_items > 0 ? Math.round((s.completed_items / s.total_items) * 100) : 0;
                  return (
                    <TableRow key={it.id}>
                      <TableCell className="font-medium">{it.name}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {it.start_date} → {it.end_date}
                      </TableCell>
                      <TableCell className="text-right">{s?.completed_items ?? 0} / {s?.total_items ?? 0}</TableCell>
                      <TableCell className="text-right">{s?.completed_points ?? 0} / {s?.total_points ?? 0}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-2 w-20 rounded-full bg-muted">
                            <div className="h-2 rounded-full bg-primary" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-xs">{pct}%</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Work Items</h3>
          <div className="flex items-center gap-2">
            <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v === "__all__" ? "" : v); setPage(1); }}>
              <SelectTrigger className="w-36"><SelectValue placeholder="All types" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All types</SelectItem>
                <SelectItem value="epic">Epic</SelectItem>
                <SelectItem value="feature">Feature</SelectItem>
                <SelectItem value="user_story">User Story</SelectItem>
                <SelectItem value="task">Task</SelectItem>
                <SelectItem value="bug">Bug</SelectItem>
              </SelectContent>
            </Select>
            <Select value={stateFilter} onValueChange={(v) => { setStateFilter(v === "__all__" ? "" : v); setPage(1); }}>
              <SelectTrigger className="w-36"><SelectValue placeholder="All states" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All states</SelectItem>
                <SelectItem value="New">New</SelectItem>
                <SelectItem value="Active">Active</SelectItem>
                <SelectItem value="Resolved">Resolved</SelectItem>
                <SelectItem value="Closed">Closed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {wiLoading && <p className="text-muted-foreground animate-pulse">Loading work items...</p>}

        {workItemsData && (
          <>
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">ID</TableHead>
                    <TableHead className="w-24">Type</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead className="w-24">State</TableHead>
                    <TableHead className="w-20 text-right">Points</TableHead>
                    <TableHead className="w-24">Priority</TableHead>
                    <TableHead className="w-10"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workItemsData.items.map((wi) => (
                    <TableRow key={wi.id}>
                      <TableCell className="text-xs text-muted-foreground">#{wi.platform_work_item_id}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={`text-[10px] ${TYPE_COLORS[wi.work_item_type] || ""}`}>
                          {TYPE_LABELS[wi.work_item_type] || wi.work_item_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium max-w-md truncate" title={wi.title}>{wi.title}</TableCell>
                      <TableCell><StateTag state={wi.state} /></TableCell>
                      <TableCell className="text-right">{wi.story_points ?? "—"}</TableCell>
                      <TableCell className="text-xs">{wi.priority ? `P${wi.priority}` : "—"}</TableCell>
                      <TableCell>
                        {wi.platform_url && (
                          <a href={wi.platform_url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground">
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {workItemsData.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                        No work items found. Sync from Azure DevOps to get started.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Card>
            {totalPages > 1 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, workItemsData.total)} of {workItemsData.total}
                </p>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm px-2">Page {page} of {totalPages}</span>
                  <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

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
                    <ViewLogsButton logUrl={api.getDeliverySyncLogUrl(projectId)} />
                  </TableCell>
                </TableRow>
              ))}
              {syncJobs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                    No sync jobs yet. Click &quot;Sync from Azure DevOps&quot; to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>
      </div>
    </div>
  );
}
