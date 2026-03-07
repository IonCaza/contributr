"use client";

import { useMemo } from "react";
import Link from "next/link";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { VelocityBarChart } from "@/components/charts/velocity-bar-chart";
import { ThroughputChart } from "@/components/charts/throughput-chart";
import { CycleTimeHistogram } from "@/components/charts/cycle-time-histogram";
import { BugTrendChart } from "@/components/charts/bug-trend-chart";
import { StaleBacklogChart } from "@/components/charts/stale-backlog-chart";
import { BacklogTypeChart } from "@/components/charts/backlog-type-chart";
import type {
  DeliveryStats,
  FlowMetrics,
  QualityMetrics,
  IntersectionMetrics,
  BacklogHealthMetrics,
  WorkItemDetailRow,
  ContributorDeliverySummary,
} from "@/lib/types";

interface DeliveryDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  metric: string;
  projectId: string;
  stats?: DeliveryStats;
  flow?: FlowMetrics;
  quality?: QualityMetrics;
  intersection?: IntersectionMetrics;
  backlog?: BacklogHealthMetrics;
  items?: WorkItemDetailRow[];
  contributors?: ContributorDeliverySummary[];
  itemsLoading?: boolean;
  contributorsLoading?: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  epic: "Epic",
  feature: "Feature",
  user_story: "User Story",
  task: "Task",
  bug: "Bug",
};

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border p-3 text-center">
      <div className="text-lg font-bold">{typeof value === "number" ? value.toLocaleString() : value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function ItemTable({
  items,
  columns,
}: {
  items: WorkItemDetailRow[];
  columns: { key: string; label: string; render?: (item: WorkItemDetailRow) => React.ReactNode }[];
}) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No items to display.</p>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((c) => (
            <TableHead key={c.key}>{c.label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            {columns.map((c) => (
              <TableCell key={c.key}>
                {c.render ? c.render(item) : (item as unknown as Record<string, unknown>)[c.key]?.toString() ?? "—"}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ContributorTable({ data }: { data: ContributorDeliverySummary[] }) {
  if (!data.length) return <p className="text-sm text-muted-foreground">No contributor data.</p>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Contributor</TableHead>
          <TableHead className="text-right">Items</TableHead>
          <TableHead className="text-right">Completed</TableHead>
          <TableHead className="text-right">SP</TableHead>
          <TableHead className="text-right">Avg Cycle</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((c) => (
          <TableRow key={c.contributor_id}>
            <TableCell>
              <Link href={`/contributors/${c.contributor_id}`} className="text-primary hover:underline">
                {c.contributor_name ?? "Unknown"}
              </Link>
            </TableCell>
            <TableCell className="text-right">{c.total_items}</TableCell>
            <TableCell className="text-right">{c.completed_items}</TableCell>
            <TableCell className="text-right">{c.completed_sp}</TableCell>
            <TableCell className="text-right">{c.avg_cycle_time_hours != null ? `${c.avg_cycle_time_hours}h` : "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function LoadingRows() {
  return <p className="text-sm text-muted-foreground animate-pulse py-4">Loading detail data...</p>;
}

function idCol(item: WorkItemDetailRow) {
  return (
    <span className="font-mono text-xs text-muted-foreground">#{item.platform_work_item_id}</span>
  );
}
function typeCol(item: WorkItemDetailRow) {
  return <Badge variant="outline" className="text-xs">{TYPE_LABELS[item.work_item_type] ?? item.work_item_type}</Badge>;
}
function titleCol(item: WorkItemDetailRow) {
  return <span className="line-clamp-1">{item.title}</span>;
}
function assigneeCol(item: WorkItemDetailRow) {
  return item.assigned_to_name ?? "Unassigned";
}

export function DeliveryDetailSheet({
  open,
  onOpenChange,
  title,
  metric,
  stats,
  flow,
  quality,
  intersection,
  backlog,
  items,
  contributors,
  itemsLoading,
  contributorsLoading,
}: DeliveryDetailSheetProps) {
  const openItems = useMemo(() => {
    if (!items) return [];
    const openStates = new Set(["New", "Active", "Committed", "In Progress", "Approved"]);
    return items.filter((i) => openStates.has(i.state));
  }, [items]);

  const completedItems = useMemo(() => {
    if (!items) return [];
    const doneStates = new Set(["Resolved", "Closed", "Done", "Completed"]);
    return items.filter((i) => doneStates.has(i.state));
  }, [items]);

  const bugItems = useMemo(() => {
    if (!items) return [];
    return items.filter((i) => i.work_item_type === "bug");
  }, [items]);

  const linkedItems = useMemo(() => {
    if (!items) return [];
    return items.filter((i) => i.linked_commit_count > 0);
  }, [items]);

  const unlinkedItems = useMemo(() => {
    if (!items) return [];
    return items.filter((i) => i.linked_commit_count === 0);
  }, [items]);

  const itemsWithCycleTime = useMemo(() => {
    if (!items) return [];
    return items.filter((i) => i.cycle_time_hours != null).sort((a, b) => (b.cycle_time_hours ?? 0) - (a.cycle_time_hours ?? 0));
  }, [items]);

  const itemsWithLeadTime = useMemo(() => {
    if (!items) return [];
    return items.filter((i) => i.lead_time_hours != null).sort((a, b) => (b.lead_time_hours ?? 0) - (a.lead_time_hours ?? 0));
  }, [items]);

  const byContributorSorted = useMemo(() => {
    if (!contributors) return [];
    return [...contributors].sort((a, b) => b.completed_items - a.completed_items);
  }, [contributors]);

  const byContributorSP = useMemo(() => {
    if (!contributors) return [];
    return [...contributors].sort((a, b) => b.completed_sp - a.completed_sp);
  }, [contributors]);

  function renderContent() {
    switch (metric) {
      case "work_items": {
        const byType: Record<string, number> = {};
        const byState: Record<string, number> = {};
        items?.forEach((i) => {
          byType[i.work_item_type] = (byType[i.work_item_type] || 0) + 1;
          byState[i.state] = (byState[i.state] || 0) + 1;
        });
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Total" value={stats?.total_work_items ?? items?.length ?? 0} />
              <StatBox label="Open" value={stats?.open_items ?? openItems.length} />
              <StatBox label="Completed" value={stats?.completed_items ?? completedItems.length} />
            </div>
            {stats?.backlog_by_type && stats.backlog_by_type.length > 0 && (
              <BacklogTypeChart data={stats.backlog_by_type} />
            )}
            <h4 className="text-sm font-medium mt-2">By Contributor</h4>
            {contributorsLoading ? <LoadingRows /> : <ContributorTable data={byContributorSorted} />}
          </>
        );
      }

      case "open_items": {
        const sorted = [...openItems].sort((a, b) => {
          const ageA = a.created_at ? Date.now() - new Date(a.created_at).getTime() : 0;
          const ageB = b.created_at ? Date.now() - new Date(b.created_at).getTime() : 0;
          return ageB - ageA;
        });
        const avgAgeDays = sorted.length > 0
          ? Math.round(sorted.reduce((sum, i) => sum + (i.created_at ? (Date.now() - new Date(i.created_at).getTime()) / 86400000 : 0), 0) / sorted.length)
          : 0;
        const oldestDays = sorted.length > 0 && sorted[0].created_at
          ? Math.round((Date.now() - new Date(sorted[0].created_at).getTime()) / 86400000)
          : 0;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Open Items" value={openItems.length} />
              <StatBox label="Avg Age" value={`${avgAgeDays}d`} />
              <StatBox label="Oldest" value={`${oldestDays}d`} />
            </div>
            {backlog?.age_distribution && backlog.age_distribution.length > 0 && (
              <StaleBacklogChart data={backlog.age_distribution} title="Age Distribution" />
            )}
            <h4 className="text-sm font-medium mt-2">Open Items (oldest first)</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={sorted.slice(0, 20)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "type", label: "Type", render: typeCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "assigned_to_name", label: "Assignee", render: assigneeCol },
                  { key: "age", label: "Age", render: (i) => i.created_at ? `${Math.round((Date.now() - new Date(i.created_at).getTime()) / 86400000)}d` : "—" },
                ]}
              />
            )}
          </>
        );
      }

      case "completed": {
        const sorted = [...completedItems].sort((a, b) => {
          const da = a.resolved_at ? new Date(a.resolved_at).getTime() : 0;
          const db2 = b.resolved_at ? new Date(b.resolved_at).getTime() : 0;
          return db2 - da;
        });
        const velTrend = stats?.velocity_trend ?? [];
        const thisSprintCompleted = velTrend.length > 0 ? velTrend[velTrend.length - 1].points : 0;
        const avgPerSprint = velTrend.length > 0 ? Math.round(velTrend.reduce((s, v) => s + v.points, 0) / velTrend.length) : 0;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Completed" value={completedItems.length} />
              <StatBox label="Latest Sprint" value={`${thisSprintCompleted} SP`} />
              <StatBox label="Avg / Sprint" value={`${avgPerSprint} SP`} />
            </div>
            {stats?.throughput_trend && stats.throughput_trend.length > 0 && (
              <ThroughputChart data={stats.throughput_trend.slice(-30)} title="Recent Completion Trend" />
            )}
            <h4 className="text-sm font-medium mt-2">Top Completers</h4>
            {contributorsLoading ? <LoadingRows /> : <ContributorTable data={byContributorSorted} />}
          </>
        );
      }

      case "story_points": {
        const velTrend = stats?.velocity_trend ?? [];
        const avgVel = velTrend.length > 0 ? Math.round(velTrend.reduce((s, v) => s + v.points, 0) / velTrend.length * 10) / 10 : 0;
        const completionPct = stats && stats.total_story_points > 0
          ? Math.round((stats.completed_story_points / stats.total_story_points) * 100)
          : 0;
        return (
          <>
            <div className="grid grid-cols-4 gap-3">
              <StatBox label="Completed SP" value={stats?.completed_story_points ?? 0} />
              <StatBox label="Total SP" value={stats?.total_story_points ?? 0} />
              <StatBox label="Avg / Sprint" value={avgVel} />
              <StatBox label="Completion" value={`${completionPct}%`} />
            </div>
            {velTrend.length > 0 && <VelocityBarChart data={velTrend} title="Velocity by Sprint" />}
            <h4 className="text-sm font-medium mt-2">Contributors by Story Points</h4>
            {contributorsLoading ? <LoadingRows /> : <ContributorTable data={byContributorSP} />}
          </>
        );
      }

      case "cycle_time": {
        const sorted = itemsWithCycleTime;
        const times = sorted.map((i) => i.cycle_time_hours!);
        const median = times.length > 0 ? times[Math.floor(times.length / 2)] : 0;
        const mean = times.length > 0 ? Math.round(times.reduce((s, t) => s + t, 0) / times.length * 10) / 10 : 0;
        const p90 = times.length > 0 ? times[Math.floor(times.length * 0.1)] : 0;
        return (
          <>
            <div className="grid grid-cols-4 gap-3">
              <StatBox label="Median" value={`${Math.round(median)}h`} />
              <StatBox label="Mean" value={`${mean}h`} />
              <StatBox label="P90" value={`${Math.round(p90)}h`} />
              <StatBox label="Sample" value={times.length} />
            </div>
            {flow?.cycle_time_distribution && flow.cycle_time_distribution.length > 0 && (
              <CycleTimeHistogram data={flow.cycle_time_distribution} />
            )}
            <h4 className="text-sm font-medium mt-2">Slowest Items</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={sorted.slice(0, 15)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "type", label: "Type", render: typeCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "cycle_time", label: "Cycle Time", render: (i) => `${i.cycle_time_hours}h` },
                ]}
              />
            )}
          </>
        );
      }

      case "lead_time": {
        const sorted = itemsWithLeadTime;
        const times = sorted.map((i) => i.lead_time_hours!);
        const median = times.length > 0 ? times[Math.floor(times.length / 2)] : 0;
        const mean = times.length > 0 ? Math.round(times.reduce((s, t) => s + t, 0) / times.length * 10) / 10 : 0;
        const p90 = times.length > 0 ? times[Math.floor(times.length * 0.1)] : 0;
        return (
          <>
            <div className="grid grid-cols-4 gap-3">
              <StatBox label="Median" value={`${Math.round(median)}h`} />
              <StatBox label="Mean" value={`${mean}h`} />
              <StatBox label="P90" value={`${Math.round(p90)}h`} />
              <StatBox label="Sample" value={times.length} />
            </div>
            <h4 className="text-sm font-medium mt-2">Slowest Items (lead time)</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={sorted.slice(0, 15)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "type", label: "Type", render: typeCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "lead_time", label: "Lead Time", render: (i) => `${i.lead_time_hours}h` },
                ]}
              />
            )}
          </>
        );
      }

      case "avg_velocity": {
        const velTrend = stats?.velocity_trend ?? [];
        const points = velTrend.map((v) => v.points);
        const avg = points.length > 0 ? Math.round(points.reduce((s, p) => s + p, 0) / points.length * 10) / 10 : 0;
        const best = points.length > 0 ? Math.max(...points) : 0;
        const worst = points.length > 0 ? Math.min(...points) : 0;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Avg SP / Sprint" value={avg} />
              <StatBox label="Best Sprint" value={best} />
              <StatBox label="Lowest Sprint" value={worst} />
            </div>
            {velTrend.length > 0 && <VelocityBarChart data={velTrend} />}
            <h4 className="text-sm font-medium mt-2">Contributors by SP</h4>
            {contributorsLoading ? <LoadingRows /> : <ContributorTable data={byContributorSP} />}
          </>
        );
      }

      case "avg_throughput": {
        const trend = stats?.throughput_trend ?? [];
        const completed = trend.reduce((s, t) => s + t.completed, 0);
        const avgPerDay = trend.length > 0 ? Math.round(completed / trend.length * 10) / 10 : 0;
        const peakDay = trend.length > 0 ? Math.max(...trend.map((t) => t.completed)) : 0;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Avg / Day" value={avgPerDay} />
              <StatBox label="Total Completed" value={completed} />
              <StatBox label="Peak Day" value={peakDay} />
            </div>
            {trend.length > 0 && <ThroughputChart data={trend} />}
            <h4 className="text-sm font-medium mt-2">Top Completers</h4>
            {contributorsLoading ? <LoadingRows /> : <ContributorTable data={byContributorSorted} />}
          </>
        );
      }

      case "stale_items": {
        const staleItems = items?.filter((i) => {
          if (!i.updated_at) return false;
          const doneStates = new Set(["Resolved", "Closed", "Done", "Completed"]);
          if (doneStates.has(i.state)) return false;
          return (Date.now() - new Date(i.updated_at).getTime()) > 30 * 86400000;
        }) ?? [];
        const sorted = [...staleItems].sort((a, b) => {
          const ua = a.updated_at ? new Date(a.updated_at).getTime() : Infinity;
          const ub = b.updated_at ? new Date(b.updated_at).getTime() : Infinity;
          return ua - ub;
        });
        const byType: Record<string, number> = {};
        sorted.forEach((i) => { byType[i.work_item_type] = (byType[i.work_item_type] || 0) + 1; });
        const oldestDays = sorted.length > 0 && sorted[0].updated_at
          ? Math.round((Date.now() - new Date(sorted[0].updated_at).getTime()) / 86400000)
          : 0;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Stale Items" value={sorted.length} />
              <StatBox label="Types" value={Object.keys(byType).length} />
              <StatBox label="Oldest" value={`${oldestDays}d`} />
            </div>
            {backlog?.stale_items && backlog.stale_items.length > 0 && (
              <StaleBacklogChart data={backlog.stale_items} title="Stale by Type" />
            )}
            <h4 className="text-sm font-medium mt-2">Stale Items (least recently updated)</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={sorted.slice(0, 20)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "type", label: "Type", render: typeCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "last_update", label: "Last Update", render: (i) => i.updated_at ? `${Math.round((Date.now() - new Date(i.updated_at).getTime()) / 86400000)}d ago` : "—" },
                ]}
              />
            )}
          </>
        );
      }

      case "net_growth": {
        const growth = backlog?.growth ?? [];
        const totalCreated = growth.reduce((s, g) => s + g.created, 0);
        const totalCompleted = growth.reduce((s, g) => s + g.completed, 0);
        const net = totalCreated - totalCompleted;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Created (period)" value={totalCreated} />
              <StatBox label="Completed (period)" value={totalCompleted} />
              <StatBox label="Net Growth" value={net > 0 ? `+${net}` : `${net}`} />
            </div>
            {growth.length > 0 && (
              <ThroughputChart
                data={growth.map((g) => ({ date: g.date, created: g.created, completed: g.completed }))}
                title="Backlog Growth (Created vs Completed)"
              />
            )}
          </>
        );
      }

      case "bug_resolution": {
        const bugsWithTime = bugItems
          .filter((i) => i.cycle_time_hours != null)
          .sort((a, b) => (b.cycle_time_hours ?? 0) - (a.cycle_time_hours ?? 0));
        const openBugs = bugItems.filter((i) => {
          const doneStates = new Set(["Resolved", "Closed", "Done", "Completed"]);
          return !doneStates.has(i.state);
        });
        return (
          <>
            <div className="grid grid-cols-4 gap-3">
              <StatBox label="Median" value={quality?.resolution_time ? `${quality.resolution_time.median_hours}h` : "—"} />
              <StatBox label="P90" value={quality?.resolution_time ? `${quality.resolution_time.p90_hours}h` : "—"} />
              <StatBox label="Sample" value={quality?.resolution_time?.sample_size ?? bugsWithTime.length} />
              <StatBox label="Open Bugs" value={openBugs.length} />
            </div>
            {quality?.bug_trend && quality.bug_trend.length > 0 && (
              <BugTrendChart data={quality.bug_trend} />
            )}
            <h4 className="text-sm font-medium mt-2">Bugs by Resolution Time</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={bugsWithTime.slice(0, 15)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "state", label: "State" },
                  { key: "resolution", label: "Resolution", render: (i) => i.cycle_time_hours != null ? `${i.cycle_time_hours}h` : "—" },
                ]}
              />
            )}
          </>
        );
      }

      case "defect_density": {
        const byState: Record<string, number> = {};
        bugItems.forEach((i) => { byState[i.state] = (byState[i.state] || 0) + 1; });
        const stateData = Object.entries(byState).map(([state, count]) => ({ state, count }));
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Bugs" value={quality?.defect_density?.bugs ?? bugItems.length} />
              <StatBox label="Total Items" value={quality?.defect_density?.total ?? items?.length ?? 0} />
              <StatBox label="Density" value={quality?.defect_density ? `${(quality.defect_density.ratio * 100).toFixed(1)}%` : "—"} />
            </div>
            {stateData.length > 0 && (
              <div className="space-y-2 mt-2">
                <h4 className="text-sm font-medium">Bugs by State</h4>
                <div className="grid grid-cols-2 gap-2">
                  {stateData.map((s) => (
                    <div key={s.state} className="flex justify-between rounded border px-3 py-2 text-sm">
                      <span>{s.state}</span>
                      <span className="font-medium">{s.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <h4 className="text-sm font-medium mt-2">All Bugs</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={bugItems.slice(0, 20)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "state", label: "State" },
                  { key: "assigned_to_name", label: "Assignee", render: assigneeCol },
                ]}
              />
            )}
          </>
        );
      }

      case "link_coverage": {
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Linked" value={intersection?.total_linked_items ?? linkedItems.length} />
              <StatBox label="Unlinked" value={(intersection?.total_items ?? 0) - (intersection?.total_linked_items ?? 0)} />
              <StatBox label="Coverage" value={intersection ? `${intersection.link_coverage_pct.toFixed(1)}%` : "—"} />
            </div>
            <h4 className="text-sm font-medium mt-4">Unlinked Items (need code links)</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={unlinkedItems.slice(0, 20)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "type", label: "Type", render: typeCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "state", label: "State" },
                ]}
              />
            )}
          </>
        );
      }

      case "commits_per_sp": {
        const withSP = (items ?? [])
          .filter((i) => i.story_points && i.story_points > 0)
          .map((i) => ({ ...i, ratio: i.linked_commit_count / i.story_points! }))
          .sort((a, b) => b.ratio - a.ratio);
        const avgRatio = intersection?.commits_per_story_point ?? 0;
        const maxRatio = withSP.length > 0 ? Math.round(withSP[0].ratio * 10) / 10 : 0;
        const zeroCommit = (items ?? []).filter((i) => i.linked_commit_count === 0 && i.story_points && i.story_points > 0).length;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Average" value={avgRatio.toFixed(1)} />
              <StatBox label="Max Ratio" value={maxRatio} />
              <StatBox label="0 Commits (with SP)" value={zeroCommit} />
            </div>
            <h4 className="text-sm font-medium mt-4">Items by Commits/SP Ratio</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={withSP.slice(0, 15)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "sp", label: "SP", render: (i) => `${i.story_points ?? 0}` },
                  { key: "commits", label: "Commits", render: (i) => `${i.linked_commit_count}` },
                  { key: "ratio", label: "Ratio", render: (i) => i.story_points ? `${(i.linked_commit_count / i.story_points).toFixed(1)}` : "—" },
                ]}
              />
            )}
          </>
        );
      }

      case "commit_to_resolution": {
        const withFCR = (items ?? [])
          .filter((i) => i.first_commit_to_resolution_hours != null)
          .sort((a, b) => (b.first_commit_to_resolution_hours ?? 0) - (a.first_commit_to_resolution_hours ?? 0));
        const times = withFCR.map((i) => i.first_commit_to_resolution_hours!);
        const avg = times.length > 0 ? Math.round(times.reduce((s, t) => s + t, 0) / times.length) : 0;
        const median = times.length > 0 ? Math.round(times[Math.floor(times.length / 2)]) : 0;
        const p90Val = times.length > 0 ? Math.round(times[Math.floor(times.length * 0.1)]) : 0;
        return (
          <>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Average" value={`${avg}h`} />
              <StatBox label="Median" value={`${median}h`} />
              <StatBox label="P90" value={`${p90Val}h`} />
            </div>
            <h4 className="text-sm font-medium mt-4">Items by First-Commit to Resolution</h4>
            {itemsLoading ? <LoadingRows /> : (
              <ItemTable
                items={withFCR.slice(0, 15)}
                columns={[
                  { key: "id", label: "ID", render: idCol },
                  { key: "type", label: "Type", render: typeCol },
                  { key: "title", label: "Title", render: titleCol },
                  { key: "fcr", label: "FC → Resolved", render: (i) => `${i.first_commit_to_resolution_hours}h` },
                ]}
              />
            )}
          </>
        );
      }

      default:
        return <p className="text-sm text-muted-foreground">No drill-down available for this metric.</p>;
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <div className="space-y-6 px-4 pb-6">
          {renderContent()}
        </div>
      </SheetContent>
    </Sheet>
  );
}
