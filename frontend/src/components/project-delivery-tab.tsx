"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import Link from "next/link";
import {
  RefreshCw,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  Search,
  Eraser,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/stat-card";
import { StatRowSkeleton, ChartSkeleton, TableSkeleton } from "@/components/page-skeleton";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { ViewLogsButton } from "@/components/sync-log-viewer";
import { VelocityBarChart } from "@/components/charts/velocity-bar-chart";
import { ThroughputChart } from "@/components/charts/throughput-chart";
import { BacklogTypeChart } from "@/components/charts/backlog-type-chart";
import { BacklogStateChart } from "@/components/charts/backlog-state-chart";
import { BacklogFunnelChart } from "@/components/charts/backlog-funnel-chart";
import { CycleTimeHistogram } from "@/components/charts/cycle-time-histogram";
import { CumulativeFlowChart } from "@/components/charts/cumulative-flow-chart";
import { BugTrendChart } from "@/components/charts/bug-trend-chart";
import { StaleBacklogChart } from "@/components/charts/stale-backlog-chart";
import { WIPChart } from "@/components/charts/wip-chart";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import {
  useDeliveryStats,
  useWorkItems,
  useWorkItemsTree,
  useIterations,
  useTriggerDeliverySync,
  usePurgeDelivery,
  useDeliverySyncJobs,
  useFlowMetrics,
  useBacklogHealth,
  useQualityMetrics,
  useIntersectionMetrics,
  useItemDetails,
  useContributorDeliverySummary,
} from "@/hooks/use-delivery";
import { DeliveryDetailSheet, type DrillDownFilter } from "@/components/delivery-detail-sheet";
import { WorkItemsTreeView } from "@/components/work-items-tree-view";
import { TrustedBacklogCard } from "@/components/delivery/trusted-backlog-card";
import { FeatureRollupCard } from "@/components/delivery/feature-rollup-card";
import { SizingTrendCard } from "@/components/delivery/sizing-trend-card";
import { LongRunningStoriesCard } from "@/components/delivery/long-running-stories-card";
import { CarryoverTab } from "@/components/delivery/carryover-tab";
import type { DeliveryFilters } from "@/lib/types";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

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
  if (lower.includes("active") || lower.includes("progress"))
    cls = "bg-blue-500/10 text-blue-700 dark:text-blue-400";
  else if (lower.includes("resolved") || lower.includes("done") || lower.includes("completed"))
    cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed"))
    cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new"))
    cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return <Badge variant="secondary" className={`text-[10px] ${cls}`}>{state}</Badge>;
}

function EmptyState({ message }: { message: string }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{message}</p>;
}


// ── Main Component ──────────────────────────────────────────────────

export function ProjectDeliveryTab({ projectId }: { projectId: string }) {
  // ── Filter state ────────────────────────────────────────────────
  const [dateRange, setDateRange] = useState<DateRange>(() => defaultRange());
  const [sprintAlign, setSprintAlign] = useState<string>("");

  const deliveryFilters = useMemo<DeliveryFilters>(
    () => ({
      from_date: dateRange.from || undefined,
      to_date: dateRange.to || undefined,
    }),
    [dateRange],
  );

  // ── Work item local filters ─────────────────────────────────────
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [stateFilter, setStateFilter] = useState<string>("");
  const [wiSearch, setWiSearch] = useState<string>("");
  const debouncedSearch = useDebouncedValue(wiSearch);
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const [workItemsView, setWorkItemsView] = useState<"list" | "tree">("list");
  const [sortBy, setSortBy] = useState<string>("updated_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [storyPointsMin, setStoryPointsMin] = useState<string>("");
  const [storyPointsMax, setStoryPointsMax] = useState<string>("");
  const [resolvedFrom, setResolvedFrom] = useState<string>("");
  const [resolvedTo, setResolvedTo] = useState<string>("");
  const [closedFrom, setClosedFrom] = useState<string>("");
  const [closedTo, setClosedTo] = useState<string>("");
  const [moreFiltersOpen, setMoreFiltersOpen] = useState(false);
  const [sprintScope, setSprintScope] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("contributr:sprint_scope") || "recent";
    }
    return "recent";
  });

  // ── Sync state ──────────────────────────────────────────────────
  const qc = useQueryClient();
  const syncMutation = useTriggerDeliverySync(projectId);
  const purgeMutation = usePurgeDelivery(projectId);
  const [purgeConfirmOpen, setPurgeConfirmOpen] = useState(false);

  // ── Data hooks ──────────────────────────────────────────────────
  const { data: stats, isLoading: statsLoading } = useDeliveryStats(projectId, deliveryFilters);
  const { data: iterations, isLoading: iterationsLoading } = useIterations(projectId);
  const { data: flow, isLoading: flowLoading } = useFlowMetrics(projectId, deliveryFilters);
  const { data: backlog, isLoading: backlogLoading } = useBacklogHealth(projectId, deliveryFilters);
  const { data: quality, isLoading: qualityLoading } = useQualityMetrics(projectId, deliveryFilters);
  const { data: intersection } = useIntersectionMetrics(projectId, deliveryFilters);
  const workItemFilters = useMemo(
    () => ({
      work_item_type: typeFilter || undefined,
      state: stateFilter || undefined,
      search: debouncedSearch || undefined,
      from_date: deliveryFilters.from_date,
      to_date: deliveryFilters.to_date,
      resolved_from: resolvedFrom || undefined,
      resolved_to: resolvedTo || undefined,
      closed_from: closedFrom || undefined,
      closed_to: closedTo || undefined,
      priority: priorityFilter ? parseInt(priorityFilter, 10) : undefined,
      story_points_min: storyPointsMin ? parseFloat(storyPointsMin) : undefined,
      story_points_max: storyPointsMax ? parseFloat(storyPointsMax) : undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    }),
    [
      typeFilter,
      stateFilter,
      debouncedSearch,
      deliveryFilters.from_date,
      deliveryFilters.to_date,
      resolvedFrom,
      resolvedTo,
      closedFrom,
      closedTo,
      priorityFilter,
      storyPointsMin,
      storyPointsMax,
      sortBy,
      sortOrder,
    ],
  );
  const { data: workItemsData, isLoading: wiLoading } = useWorkItems(projectId, {
    ...workItemFilters,
    page,
    page_size: pageSize,
  });
  const { data: workItemsTreeData, isLoading: wiTreeLoading } = useWorkItemsTree(
    projectId,
    { ...workItemFilters, max_items: 2000 },
    { enabled: workItemsView === "tree" },
  );
  const { data: syncJobs = [] } = useDeliverySyncJobs(projectId);
  const syncing = syncJobs.some((j) => j.status === "queued" || j.status === "running");

  // ── Drill-down state ───────────────────────────────────────────
  const [drillDown, setDrillDown] = useState<{ title: string; metric: string; filter?: DrillDownFilter } | null>(null);
  const { data: itemDetailRows, isLoading: itemDetailsLoading } = useItemDetails(projectId, deliveryFilters, !!drillDown);
  const { data: contribSummary, isLoading: contribSummaryLoading } = useContributorDeliverySummary(projectId, deliveryFilters, !!drillDown);

  useRegisterUIContext("delivery", {
    stats,
    flow,
    backlog,
    quality,
    iterations: iterations?.slice(0, 5),
    filters: deliveryFilters,
  });

  // ── Refresh delivery data when sync finishes ───────────────────
  const wasSyncing = useRef(false);
  useEffect(() => {
    if (syncing) {
      wasSyncing.current = true;
    } else if (wasSyncing.current) {
      wasSyncing.current = false;
      qc.invalidateQueries({ queryKey: ["delivery", projectId] });
    }
  }, [syncing, qc, projectId]);

  const handleSync = useCallback(() => {
    syncMutation.mutate();
  }, [syncMutation]);

  const handlePurgeDelivery = useCallback(() => {
    purgeMutation.mutate(undefined, {
      onSuccess: () => setPurgeConfirmOpen(false),
    });
  }, [purgeMutation]);

  // ── Derived data ────────────────────────────────────────────────
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

  const scopedIterations = useMemo(() => {
    if (sprintScope === "all") return sortedIterations;
    const active = sortedIterations.filter((it) => it._status === "active");
    const past = sortedIterations.filter((it) => it._status === "past");
    if (sprintScope === "active_and_past") return [...active, ...past];
    const upcoming = sortedIterations.filter((it) => it._status === "upcoming").slice(0, 3);
    return [...active, ...upcoming, ...past.slice(0, 3)];
  }, [sortedIterations, sprintScope]);

  const totalPages = workItemsData ? Math.ceil(workItemsData.total / pageSize) : 0;
  const showIntegration = intersection && intersection.total_linked_items > 0;

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

  return (
    <div className="space-y-6">
      {/* ── Global Filter Bar ──────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        {iterationsLoading ? (
          <Skeleton className="h-9 w-72 rounded-md" />
        ) : sortedIterations.length > 0 ? (
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
        ) : null}

        <div className="h-5 w-px bg-border" />

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

      {/* ── Metric Tabs ────────────────────────────────────────────── */}
      <Tabs defaultValue="overview" className="space-y-4">
        <div className="flex items-center justify-between">
          <TabsList variant="line">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="velocity">Velocity &amp; Throughput</TabsTrigger>
            <TabsTrigger value="flow">Flow</TabsTrigger>
            <TabsTrigger value="backlog">Backlog Health</TabsTrigger>
            <TabsTrigger value="carryover">Carry-over</TabsTrigger>
            <TabsTrigger value="quality">Quality</TabsTrigger>
            {showIntegration && <TabsTrigger value="integration">Integration</TabsTrigger>}
          </TabsList>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSync}
            disabled={syncMutation.isPending || syncing}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${syncMutation.isPending || syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing..." : "Sync from Azure DevOps"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-amber-600 border-amber-200 hover:bg-amber-50 hover:text-amber-700 dark:border-amber-800 dark:hover:bg-amber-950/50"
            onClick={() => setPurgeConfirmOpen(true)}
            disabled={purgeMutation.isPending || syncing}
          >
            <Eraser className="mr-2 h-4 w-4" />
            Purge
          </Button>
        </div>

        <AlertDialog open={purgeConfirmOpen} onOpenChange={setPurgeConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Purge delivery data</AlertDialogTitle>
              <AlertDialogDescription>
                This will permanently delete all delivery data for this project — work items, iterations, teams, sync history, and statistics. You can re-sync from Azure DevOps afterward. This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handlePurgeDelivery}
                className="bg-amber-600 text-white hover:bg-amber-700"
              >
                {purgeMutation.isPending ? "Purging..." : "Purge data"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* ── Overview Tab ──────────────────────────────────────────── */}
        <TabsContent value="overview" className="space-y-4">
          {statsLoading && (
            <>
              <StatRowSkeleton count={4} />
              <StatRowSkeleton count={2} />
              <div className="grid gap-4 md:grid-cols-2">
                <ChartSkeleton />
                <ChartSkeleton />
              </div>
            </>
          )}
          {stats && (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard className={ANIM_CARD} style={stagger(0)} title="Total Work Items" value={stats.total_work_items} tooltip="Total work items tracked in this project" onClick={() => setDrillDown({ title: "Total Work Items", metric: "work_items" })} />
                <StatCard className={ANIM_CARD} style={stagger(1)} title="Open Items" value={stats.open_items} tooltip="Work items in an active/new state" onClick={() => setDrillDown({ title: "Open Items", metric: "open_items" })} />
                <StatCard className={ANIM_CARD} style={stagger(2)} title="Completed" value={stats.completed_items} tooltip="Work items resolved or closed" onClick={() => setDrillDown({ title: "Completed", metric: "completed" })} />
                <StatCard className={ANIM_CARD} style={stagger(3)}
                  title="Story Points Completed"
                  value={stats.completed_story_points}
                  subtitle={`of ${stats.total_story_points} total`}
                  tooltip="Sum of story points on resolved/closed items"
                  onClick={() => setDrillDown({ title: "Story Points", metric: "story_points" })}
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <StatCard className={ANIM_CARD} style={stagger(4)}
                  title="Avg Cycle Time"
                  value={`${stats.avg_cycle_time_hours}h`}
                  subtitle="Activated → Resolved"
                  tooltip="Median hours from active to resolved. Sparkline shows weekly trend."
                  sparklineData={stats.cycle_time_trend?.map((t) => t.median_hours)}
                  onClick={() => setDrillDown({ title: "Avg Cycle Time", metric: "cycle_time" })}
                />
                <StatCard className={ANIM_CARD} style={stagger(5)}
                  title="Avg Lead Time"
                  value={`${stats.avg_lead_time_hours}h`}
                  subtitle="Created → Closed"
                  tooltip="Median hours from creation to closure. Sparkline shows weekly trend."
                  sparklineData={stats.lead_time_trend?.map((t) => t.median_hours)}
                  onClick={() => setDrillDown({ title: "Avg Lead Time", metric: "lead_time" })}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <TrustedBacklogCard projectId={projectId} teamId={deliveryFilters.team_id} />
                <LongRunningStoriesCard projectId={projectId} teamId={deliveryFilters.team_id} limit={10} />
              </div>

              {/* Mini charts */}
              <div className="grid gap-4 md:grid-cols-2">
                {stats.velocity_trend?.length > 0 && (
                  <VelocityBarChart data={stats.velocity_trend} title="Velocity (mini)" />
                )}
                {stats.throughput_trend?.length > 0 && (
                  <ThroughputChart data={stats.throughput_trend.slice(-30)} title="Throughput (mini)" />
                )}
              </div>
            </>
          )}
          {!statsLoading && !stats && <EmptyState message="No delivery data yet. Sync to get started." />}
        </TabsContent>

        {/* ── Velocity & Throughput Tab ─────────────────────────────── */}
        <TabsContent value="velocity" className="space-y-4">
          {statsLoading && (
            <>
              <StatRowSkeleton count={2} />
              <ChartSkeleton />
              <ChartSkeleton />
            </>
          )}
          {stats && (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <StatCard className={ANIM_CARD} style={stagger(0)}
                  title="Avg Velocity"
                  value={stats.velocity_trend?.length > 0 ? `${Math.round(stats.velocity_trend.reduce((s, v) => s + v.points, 0) / stats.velocity_trend.length * 10) / 10} SP` : "—"}
                  subtitle="Mean story points per sprint"
                  tooltip="Average story points completed per sprint"
                  onClick={() => setDrillDown({ title: "Avg Velocity", metric: "avg_velocity" })}
                />
                <StatCard className={ANIM_CARD} style={stagger(1)}
                  title="Avg Throughput"
                  value={stats.throughput_trend?.length > 0 ? `${Math.round(stats.throughput_trend.reduce((s, t) => s + t.completed, 0) / stats.throughput_trend.length * 10) / 10} / day` : "—"}
                  subtitle="Mean items completed per day"
                  tooltip="Average work items completed per day over the trend period"
                  onClick={() => setDrillDown({ title: "Avg Throughput", metric: "avg_throughput" })}
                />
              </div>

              {stats.velocity_trend?.length > 0 ? (
                <VelocityBarChart
                  data={stats.velocity_trend}
                  onIterationClick={(pt) => setDrillDown({
                    title: `Sprint: ${pt.iteration}`,
                    metric: "completed",
                    filter: { iterationName: pt.iteration },
                  })}
                />
              ) : (
                <EmptyState message="No velocity data available." />
              )}

              {stats.throughput_trend?.length > 0 ? (
                <ThroughputChart data={stats.throughput_trend} />
              ) : (
                <EmptyState message="No throughput data available." />
              )}
            </>
          )}
        </TabsContent>

        {/* ── Flow Tab ─────────────────────────────────────────────── */}
        <TabsContent value="flow" className="space-y-4">
          {flowLoading && (
            <>
              <StatRowSkeleton count={2} />
              <ChartSkeleton />
              <ChartSkeleton />
              <ChartSkeleton />
            </>
          )}
          {flow && (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <StatCard className={ANIM_CARD} style={stagger(0)}
                  title="Cycle Time (median)"
                  value={stats ? `${stats.avg_cycle_time_hours}h` : "—"}
                  subtitle="Activated → Resolved"
                  tooltip="Median cycle time across filtered items. Sparkline shows weekly trend."
                  sparklineData={stats?.cycle_time_trend?.map((t) => t.median_hours)}
                  onClick={() => setDrillDown({ title: "Cycle Time", metric: "cycle_time" })}
                />
                <StatCard className={ANIM_CARD} style={stagger(1)}
                  title="Lead Time (median)"
                  value={stats ? `${stats.avg_lead_time_hours}h` : "—"}
                  subtitle="Created → Closed"
                  tooltip="Median lead time across filtered items. Sparkline shows weekly trend."
                  sparklineData={stats?.lead_time_trend?.map((t) => t.median_hours)}
                  onClick={() => setDrillDown({ title: "Lead Time", metric: "lead_time" })}
                />
              </div>

              {flow.cycle_time_distribution?.length > 0 ? (
                <CycleTimeHistogram
                  data={flow.cycle_time_distribution}
                  onBucketClick={(b) => setDrillDown({
                    title: `Cycle Time: ${b.range}`,
                    metric: "cycle_time",
                    filter: { bucketRange: b.range },
                  })}
                />
              ) : (
                <EmptyState message="No cycle time data yet." />
              )}

              {flow.wip_by_state?.length > 0 ? (
                <WIPChart
                  data={flow.wip_by_state}
                  onStateClick={(state) => setDrillDown({
                    title: `WIP in ${state}`,
                    metric: "open_items",
                    filter: { state },
                  })}
                />
              ) : (
                <EmptyState message="No WIP data yet." />
              )}

              {flow.cumulative_flow?.data?.length > 0 ? (
                <CumulativeFlowChart
                  data={flow.cumulative_flow.data}
                  states={flow.cumulative_flow.states}
                />
              ) : (
                <EmptyState message="No cumulative flow data yet." />
              )}
            </>
          )}
          {!flowLoading && !flow && <EmptyState message="No flow metrics available." />}
        </TabsContent>

        {/* ── Backlog Health Tab ────────────────────────────────────── */}
        <TabsContent value="backlog" className="space-y-4">
          <TrustedBacklogCard projectId={projectId} teamId={deliveryFilters.team_id} />
          <FeatureRollupCard projectId={projectId} teamId={deliveryFilters.team_id} />
          <SizingTrendCard projectId={projectId} teamId={deliveryFilters.team_id} />
          <LongRunningStoriesCard projectId={projectId} teamId={deliveryFilters.team_id} />

          {backlogLoading && (
            <>
              <StatRowSkeleton count={2} />
              <div className="grid gap-4 md:grid-cols-2">
                <ChartSkeleton />
                <ChartSkeleton />
              </div>
              <ChartSkeleton />
            </>
          )}
          {(backlog || stats) && (
            <div className="grid gap-4 md:grid-cols-2">
              <StatCard className={ANIM_CARD} style={stagger(0)}
                title="Stale Items"
                value={backlog?.stale_items ? backlog.stale_items.reduce((s, i) => s + i.count, 0) : "—"}
                subtitle="Not updated in 30+ days"
                tooltip="Open work items with no updates for 30 days or more"
                onClick={() => setDrillDown({ title: "Stale Items", metric: "stale_items" })}
              />
              <StatCard className={ANIM_CARD} style={stagger(1)}
                title="Net Growth (period)"
                value={backlog?.growth ? (() => { const net = backlog.growth.reduce((s, g) => s + g.net, 0); return net > 0 ? `+${net}` : `${net}`; })() : "—"}
                subtitle="Created minus completed"
                tooltip="Net change in backlog: items created minus items completed over the filtered period"
                onClick={() => setDrillDown({ title: "Net Growth", metric: "net_growth" })}
              />
            </div>
          )}
          {stats && (
            <div className="grid gap-4 md:grid-cols-2">
              {stats.backlog_by_type?.length > 0 && (
                <BacklogTypeChart
                  data={stats.backlog_by_type}
                  onTypeClick={(type) => setDrillDown({
                    title: `Backlog: ${type}`,
                    metric: "work_items",
                    filter: { workItemType: type },
                  })}
                />
              )}
              {stats.backlog_by_state?.length > 0 && (
                <BacklogStateChart
                  data={stats.backlog_by_state}
                  onStateClick={(state) => setDrillDown({
                    title: `Backlog: ${state}`,
                    metric: "work_items",
                    filter: { state },
                  })}
                />
              )}
            </div>
          )}
          {stats && stats.backlog_by_type?.length > 0 && (
            <BacklogFunnelChart data={stats.backlog_by_type} />
          )}
          {backlog?.stale_items && backlog.stale_items.length > 0 && (
            <StaleBacklogChart
              data={backlog.stale_items}
              title="Stale Backlog Items"
              onBucketClick={(entry) => {
                if ("type" in entry) {
                  setDrillDown({
                    title: `Stale ${entry.type}`,
                    metric: "stale_items",
                    filter: { workItemType: entry.type },
                  });
                }
              }}
            />
          )}
          {backlog?.age_distribution && backlog.age_distribution.length > 0 && (
            <StaleBacklogChart
              data={backlog.age_distribution}
              title="Backlog Age Distribution"
              onBucketClick={(entry) => {
                if ("range" in entry) {
                  setDrillDown({
                    title: `Aged ${entry.range}`,
                    metric: "stale_items",
                  });
                }
              }}
            />
          )}
          {backlog?.growth && backlog.growth.length > 0 && (
            <ThroughputChart
              data={backlog.growth.map((g) => ({ date: g.date, created: g.created, completed: g.completed }))}
              title="Backlog Growth (Created vs Completed)"
            />
          )}
          {!backlogLoading && !stats?.backlog_by_type?.length && !backlog && (
            <EmptyState message="No backlog health data available." />
          )}
        </TabsContent>

        {/* ── Carry-over Tab ────────────────────────────────────────── */}
        <TabsContent value="carryover" className="space-y-4">
          <CarryoverTab
            projectId={projectId}
            teamId={deliveryFilters.team_id}
            fromDate={deliveryFilters.from_date}
            toDate={deliveryFilters.to_date}
          />
        </TabsContent>

        {/* ── Quality Tab ──────────────────────────────────────────── */}
        <TabsContent value="quality" className="space-y-4">
          {qualityLoading && (
            <>
              <ChartSkeleton />
              <StatRowSkeleton count={3} />
            </>
          )}
          {quality && (
            <>
              {quality.bug_trend?.length > 0 ? (
                <BugTrendChart data={quality.bug_trend} />
              ) : (
                <EmptyState message="No bug trend data." />
              )}

              {quality.resolution_time && (
                <div className="grid gap-4 md:grid-cols-3">
                  <StatCard className={ANIM_CARD} style={stagger(0)}
                    title="Bug Resolution (median)"
                    value={`${quality.resolution_time.median_hours ?? 0}h`}
                    subtitle={`${quality.resolution_time.sample_size ?? 0} bugs`}
                    tooltip="Median hours to resolve a bug"
                    onClick={() => setDrillDown({ title: "Bug Resolution", metric: "bug_resolution" })}
                  />
                  <StatCard className={ANIM_CARD} style={stagger(1)}
                    title="Bug Resolution (p90)"
                    value={`${quality.resolution_time.p90_hours ?? 0}h`}
                    tooltip="90th percentile bug resolution time"
                    onClick={() => setDrillDown({ title: "Bug Resolution", metric: "bug_resolution" })}
                  />
                  {quality.defect_density && (
                    <StatCard className={ANIM_CARD} style={stagger(2)}
                      title="Defect Density"
                      value={`${((quality.defect_density.ratio ?? 0) * 100).toFixed(1)}%`}
                      subtitle={`${quality.defect_density.bugs ?? 0} bugs / ${quality.defect_density.total ?? 0} items`}
                      tooltip="Percentage of work items that are bugs"
                      onClick={() => setDrillDown({ title: "Defect Density", metric: "defect_density" })}
                    />
                  )}
                </div>
              )}
            </>
          )}
          {!qualityLoading && !quality && <EmptyState message="No quality metrics available." />}
        </TabsContent>

        {/* ── Integration Tab ──────────────────────────────────────── */}
        {showIntegration && (
          <TabsContent value="integration" className="space-y-4">
            {intersection && (
              <div className="grid gap-4 md:grid-cols-3">
                <StatCard className={ANIM_CARD} style={stagger(0)}
                  title="Link Coverage"
                  value={`${intersection.link_coverage_pct.toFixed(1)}%`}
                  subtitle={`${intersection.total_linked_items} / ${intersection.total_items} items linked`}
                  tooltip="Percentage of work items linked to commits"
                  onClick={() => setDrillDown({ title: "Link Coverage", metric: "link_coverage" })}
                />
                <StatCard className={ANIM_CARD} style={stagger(1)}
                  title="Commits per Story Point"
                  value={intersection.commits_per_story_point.toFixed(1)}
                  tooltip="Average number of commits per story point"
                  onClick={() => setDrillDown({ title: "Commits per Story Point", metric: "commits_per_sp" })}
                />
                <StatCard className={ANIM_CARD} style={stagger(2)}
                  title="Avg First-Commit to Resolution"
                  value={`${intersection.avg_first_commit_to_resolution_hours.toFixed(0)}h`}
                  tooltip="Average hours from first linked commit to work item resolution"
                  onClick={() => setDrillDown({ title: "First-Commit to Resolution", metric: "commit_to_resolution" })}
                />
              </div>
            )}
          </TabsContent>
        )}
      </Tabs>

      {/* ── Bottom: Always-visible Sections ────────────────────────── */}

      {/* Iterations */}
      {sortedIterations.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base">
              Iterations ({scopedIterations.length}{sprintScope !== "all" ? ` of ${sortedIterations.length}` : ""})
            </CardTitle>
            <Select
              value={sprintScope}
              onValueChange={(v) => {
                setSprintScope(v);
                localStorage.setItem("contributr:sprint_scope", v);
              }}
            >
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="recent">Active + 3 past + 3 upcoming</SelectItem>
                <SelectItem value="active_and_past">Active and past only</SelectItem>
                <SelectItem value="all">All iterations</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sprint</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Points</TableHead>
                  <TableHead className="text-right">Progress</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scopedIterations.map((it) => {
                  const s = it.stats;
                  const pct =
                    s && s.total_items > 0
                      ? Math.round((s.completed_items / s.total_items) * 100)
                      : 0;
                  return (
                    <TableRow
                      key={it.id}
                      className={cn(
                        "cursor-pointer hover:bg-muted/50",
                        it._status === "past" && "opacity-60",
                      )}
                    >
                      <TableCell className="font-medium">
                        <Link href={`/projects/${projectId}/delivery/iterations/${it.id}`} className="hover:underline">
                          {it.name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={cn(
                            "text-[10px]",
                            it._status === "active" && "bg-green-500/10 text-green-700 dark:text-green-400",
                            it._status === "upcoming" && "bg-blue-500/10 text-blue-700 dark:text-blue-400",
                            it._status === "past" && "bg-muted text-muted-foreground",
                          )}
                        >
                          {it._status === "active" ? "Active" : it._status === "upcoming" ? "Upcoming" : "Past"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                        {it.start_date} → {it.end_date}
                      </TableCell>
                      <TableCell className="text-right">
                        {s?.completed_items ?? 0} / {s?.total_items ?? 0}
                      </TableCell>
                      <TableCell className="text-right">
                        {s?.completed_points ?? 0} / {s?.total_points ?? 0}
                      </TableCell>
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

      {/* Work Items */}
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3 shrink-0">
            <h3 className="text-lg font-semibold">Work Items</h3>
            <Tabs
              value={workItemsView}
              onValueChange={(v) => {
                if (v === "list" || v === "tree") setWorkItemsView(v);
              }}
            >
              <TabsList className="h-9">
                <TabsTrigger value="list" className="text-sm px-3">List</TabsTrigger>
                <TabsTrigger value="tree" className="text-sm px-3">Tree</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search ID or title..."
                value={wiSearch}
                onChange={(e) => { setWiSearch(e.target.value); setPage(1); }}
                className="w-52 pl-8 h-9"
              />
            </div>
            <Select
              value={typeFilter}
              onValueChange={(v) => {
                setTypeFilter(v === "__all__" ? "" : v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All types</SelectItem>
                <SelectItem value="epic">Epic</SelectItem>
                <SelectItem value="feature">Feature</SelectItem>
                <SelectItem value="user_story">User Story</SelectItem>
                <SelectItem value="task">Task</SelectItem>
                <SelectItem value="bug">Bug</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={stateFilter}
              onValueChange={(v) => {
                setStateFilter(v === "__all__" ? "" : v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="All states" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All states</SelectItem>
                <SelectItem value="New">New</SelectItem>
                <SelectItem value="Active">Active</SelectItem>
                <SelectItem value="Resolved">Resolved</SelectItem>
                <SelectItem value="Closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={sortBy}
              onValueChange={(v) => {
                setSortBy(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="updated_at">Updated</SelectItem>
                <SelectItem value="created_at">Created</SelectItem>
                <SelectItem value="resolved_at">Resolved</SelectItem>
                <SelectItem value="closed_at">Closed</SelectItem>
                <SelectItem value="story_points">Story points</SelectItem>
                <SelectItem value="priority">Priority</SelectItem>
                <SelectItem value="title">Title</SelectItem>
                <SelectItem value="platform_work_item_id">ID</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={sortOrder}
              onValueChange={(v) => {
                setSortOrder(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="desc">Desc</SelectItem>
                <SelectItem value="asc">Asc</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Collapsible open={moreFiltersOpen} onOpenChange={setMoreFiltersOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
              {moreFiltersOpen ? "Hide filters" : "More filters (priority, size, dates)"}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Priority</span>
                <Select
                  value={priorityFilter || "__all__"}
                  onValueChange={(v) => {
                    setPriorityFilter(v === "__all__" ? "" : v);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="w-28 h-9">
                    <SelectValue placeholder="All" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">All</SelectItem>
                    <SelectItem value="1">P1</SelectItem>
                    <SelectItem value="2">P2</SelectItem>
                    <SelectItem value="3">P3</SelectItem>
                    <SelectItem value="4">P4</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Points min</span>
                <Input
                  type="number"
                  min={0}
                  step={0.5}
                  placeholder="—"
                  value={storyPointsMin}
                  onChange={(e) => {
                    setStoryPointsMin(e.target.value);
                    setPage(1);
                  }}
                  className="w-20 h-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Points max</span>
                <Input
                  type="number"
                  min={0}
                  step={0.5}
                  placeholder="—"
                  value={storyPointsMax}
                  onChange={(e) => {
                    setStoryPointsMax(e.target.value);
                    setPage(1);
                  }}
                  className="w-20 h-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Resolved from</span>
                <Input
                  type="date"
                  value={resolvedFrom}
                  onChange={(e) => {
                    setResolvedFrom(e.target.value);
                    setPage(1);
                  }}
                  className="w-36 h-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Resolved to</span>
                <Input
                  type="date"
                  value={resolvedTo}
                  onChange={(e) => {
                    setResolvedTo(e.target.value);
                    setPage(1);
                  }}
                  className="w-36 h-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Closed from</span>
                <Input
                  type="date"
                  value={closedFrom}
                  onChange={(e) => {
                    setClosedFrom(e.target.value);
                    setPage(1);
                  }}
                  className="w-36 h-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground whitespace-nowrap">Closed to</span>
                <Input
                  type="date"
                  value={closedTo}
                  onChange={(e) => {
                    setClosedTo(e.target.value);
                    setPage(1);
                  }}
                  className="w-36 h-9"
                />
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {workItemsView === "tree" ? (
          <WorkItemsTreeView
            projectId={projectId}
            roots={workItemsTreeData?.roots ?? []}
            totalCount={workItemsTreeData?.total_count ?? 0}
            isLoading={wiTreeLoading}
          />
        ) : (
          <>
            {wiLoading && <TableSkeleton rows={8} cols={6} />}

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
                    <TableHead className="w-32">Assigned To</TableHead>
                    <TableHead className="w-20 text-right">Points</TableHead>
                    <TableHead className="w-24">Priority</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workItemsData.items.map((wi) => (
                    <TableRow key={wi.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell className="text-xs text-muted-foreground">
                        #{wi.platform_work_item_id}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={`text-[10px] ${TYPE_COLORS[wi.work_item_type] || ""}`}>
                          {TYPE_LABELS[wi.work_item_type] || wi.work_item_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium max-w-md truncate" title={wi.title}>
                        <Link
                          href={`/projects/${projectId}/delivery/work-items/${wi.id}`}
                          className="hover:underline"
                        >
                          {wi.title}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <StateTag state={wi.state} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground truncate max-w-[8rem]" title={wi.assigned_to?.name ?? "Unassigned"}>
                        {wi.assigned_to?.name ?? <span className="italic">Unassigned</span>}
                      </TableCell>
                      <TableCell className="text-right">{wi.story_points ?? "—"}</TableCell>
                      <TableCell className="text-xs">{wi.priority ? `P${wi.priority}` : "—"}</TableCell>
                      <TableCell>
                        {wi.platform_url && (
                          <a
                            href={wi.platform_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {workItemsData.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
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
                  Showing {(page - 1) * pageSize + 1}–
                  {Math.min(page * pageSize, workItemsData.total)} of{" "}
                  {workItemsData.total}
                </p>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm px-2">
                    Page {page} of {totalPages}
                  </span>
                  <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </>
        )}
      </div>

      {/* Recent Sync Jobs */}
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
                <TableHead className="w-16" />
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
                  <TableCell className="align-top">
                    {j.started_at ? new Date(j.started_at).toLocaleString() : "-"}
                  </TableCell>
                  <TableCell className="align-top">
                    {j.finished_at ? new Date(j.finished_at).toLocaleString() : "-"}
                  </TableCell>
                  <TableCell className="align-top max-w-xs truncate text-destructive">
                    {j.error_message || "-"}
                  </TableCell>
                  <TableCell className="align-top">
                    <ViewLogsButton logUrl={api.getDeliverySyncLogUrl(projectId, j.id)} />
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

      <DeliveryDetailSheet
        open={!!drillDown}
        onOpenChange={(v) => { if (!v) setDrillDown(null); }}
        title={drillDown?.title ?? ""}
        metric={drillDown?.metric ?? "work_items"}
        filter={drillDown?.filter ?? null}
        projectId={projectId}
        stats={stats}
        flow={flow}
        quality={quality}
        intersection={intersection}
        backlog={backlog}
        items={itemDetailRows}
        contributors={contribSummary}
        itemsLoading={itemDetailsLoading}
        contributorsLoading={contribSummaryLoading}
      />
    </div>
  );
}
