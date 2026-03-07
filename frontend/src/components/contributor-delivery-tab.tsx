"use client";

import { useState, useMemo } from "react";
import { ExternalLink, ChevronLeft, ChevronRight, ChevronDown, GitCommit } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatCard } from "@/components/stat-card";
import { MiniSparkline } from "@/components/charts/mini-sparkline";
import { useIterations, useVelocity, useDeliveryStats, useWorkItems } from "@/hooks/use-delivery";
import type { Contributor, WorkItem } from "@/lib/types";

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

function StateTag({ state }: { state: string }) {
  const lower = state.toLowerCase();
  let cls = "bg-muted text-muted-foreground";
  if (lower.includes("active") || lower.includes("progress")) cls = "bg-blue-500/10 text-blue-700 dark:text-blue-400";
  else if (lower.includes("resolved") || lower.includes("done") || lower.includes("completed")) cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed")) cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new")) cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return <Badge variant="secondary" className={`text-[10px] ${cls}`}>{state}</Badge>;
}

function LinkedCommitsRow({ workItem, projectId }: { workItem: WorkItem; projectId: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <TableRow className="group">
        <TableCell className="text-xs text-muted-foreground">#{workItem.platform_work_item_id}</TableCell>
        <TableCell>
          <Badge variant="secondary" className={`text-[10px] ${TYPE_COLORS[workItem.work_item_type] || ""}`}>
            {TYPE_LABELS[workItem.work_item_type] || workItem.work_item_type}
          </Badge>
        </TableCell>
        <TableCell className="font-medium max-w-md">
          <div className="flex items-center gap-2">
            <Link
              href={`/projects/${projectId}/delivery/work-items/${workItem.id}`}
              className="truncate hover:underline"
              title={workItem.title}
            >
              {workItem.title}
            </Link>
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() => setOpen((v) => !v)}
            >
              <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
            </Button>
          </div>
        </TableCell>
        <TableCell><StateTag state={workItem.state} /></TableCell>
        <TableCell className="text-right">{workItem.story_points ?? "—"}</TableCell>
        <TableCell>
          {workItem.platform_url && (
            <a href={workItem.platform_url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground">
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={6} className="px-6 pb-3 pt-0">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <GitCommit className="h-3 w-3" />
              <span>
                View linked commits on the{" "}
                <Link
                  href={`/projects/${projectId}/delivery/work-items/${workItem.id}`}
                  className="text-primary hover:underline"
                >
                  work item detail page
                </Link>
              </span>
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function ContributorDeliveryTab({
  contributorId,
  contributor,
}: {
  contributorId: string;
  contributor: Contributor;
}) {
  const [stateFilter, setStateFilter] = useState<string>("");
  const [selectedIteration, setSelectedIteration] = useState<string>("");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const projectIds = contributor.projects?.map((p) => p.id) || [];
  const firstProjectId = projectIds[0] || "";

  const { data: iterations } = useIterations(firstProjectId);

  const iterationFilter = selectedIteration
    ? { iteration_ids: [selectedIteration] }
    : {};

  const { data: stats } = useDeliveryStats(firstProjectId, {
    contributor_id: contributorId,
    ...iterationFilter,
  });

  const { data: workItemsData, isLoading: wiLoading } = useWorkItems(firstProjectId, {
    assignee_id: contributorId,
    state: stateFilter || undefined,
    iteration_ids: selectedIteration ? [selectedIteration] : undefined,
    page,
    page_size: pageSize,
  });

  const { data: velocityData } = useVelocity(firstProjectId);

  const completionRate = useMemo(() => {
    if (!stats || stats.total_work_items === 0) return 0;
    return Math.round((stats.completed_items / stats.total_work_items) * 100);
  }, [stats]);

  const velocitySparkline = useMemo(() => {
    if (!velocityData?.length) return [];
    const totalPoints = stats?.completed_story_points ?? 0;
    const overallTotal = velocityData.reduce((s, v) => s + v.points, 0) || 1;
    const scale = overallTotal > 0 ? totalPoints / overallTotal : 0;
    return velocityData.map((v) => Math.round(v.points * scale));
  }, [velocityData, stats]);

  const totalPages = workItemsData ? Math.ceil(workItemsData.total / pageSize) : 0;

  if (!firstProjectId) {
    return <p className="text-muted-foreground">No project associated — delivery data unavailable.</p>;
  }

  return (
    <div className="space-y-6">
      {/* Iteration selector */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">Sprint / Iteration:</span>
        <Select
          value={selectedIteration || "__all__"}
          onValueChange={(v) => {
            setSelectedIteration(v === "__all__" ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder="All iterations" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All iterations</SelectItem>
            {iterations?.map((it) => (
              <SelectItem key={it.id} value={it.id}>
                {it.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {stats && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <StatCard title="Items Assigned" value={stats.total_work_items} tooltip="Total work items assigned to this contributor" />
            <StatCard title="Open Items" value={stats.open_items} tooltip="Currently active/new items" />
            <StatCard title="Completed" value={stats.completed_items} tooltip="Resolved or closed items" />
            <StatCard
              title="Completion Rate"
              value={`${completionRate}%`}
              tooltip="Percentage of assigned items completed"
            />
            <StatCard
              title="Story Points Delivered"
              value={stats.completed_story_points}
              subtitle={`of ${stats.total_story_points} total`}
              tooltip="Story points on resolved items"
            />
            <StatCard
              title="Personal Velocity"
              value={stats.completed_story_points}
              subtitle="points completed"
              sparklineData={velocitySparkline}
              tooltip="Story points completed (velocity trend scaled from project data)"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <StatCard title="Avg Cycle Time" value={`${stats.avg_cycle_time_hours}h`} subtitle="Activated → Resolved" tooltip="Median hours from active to resolved for this contributor's items" />
            <StatCard title="Avg Lead Time" value={`${stats.avg_lead_time_hours}h`} subtitle="Created → Closed" tooltip="Median hours from creation to closure" />
          </div>
        </>
      )}

      {/* Velocity sparkline card */}
      {velocitySparkline.length > 1 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Velocity Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-24">
              <MiniSparkline data={velocitySparkline} color="var(--chart-2)" />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Estimated personal velocity based on project-level iteration data
            </p>
          </CardContent>
        </Card>
      )}

      {/* Work Items with Linked Commits */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">Work Items</h3>
            <Badge variant="outline" className="text-xs font-normal">
              <GitCommit className="h-3 w-3 mr-1" />
              Linked Commits
            </Badge>
          </div>
          <Select value={stateFilter || "__all__"} onValueChange={(v) => { setStateFilter(v === "__all__" ? "" : v); setPage(1); }}>
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
                    <TableHead className="w-10"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workItemsData.items.map((wi) => (
                    <LinkedCommitsRow
                      key={wi.id}
                      workItem={wi}
                      projectId={firstProjectId}
                    />
                  ))}
                  {workItemsData.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                        No work items assigned to this contributor.
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
    </div>
  );
}
