"use client";

import { useState, useMemo } from "react";
import { ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatCard } from "@/components/stat-card";
import { api } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";
import type { DeliveryStats, PaginatedWorkItems, Contributor } from "@/lib/types";

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

export function ContributorDeliveryTab({
  contributorId,
  contributor,
}: {
  contributorId: string;
  contributor: Contributor;
}) {
  const [stateFilter, setStateFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const projectIds = contributor.projects?.map((p) => p.id) || [];
  const firstProjectId = projectIds[0] || "";

  const { data: stats } = useQuery({
    queryKey: ["delivery", firstProjectId, "stats", { contributor_id: contributorId }],
    queryFn: () => api.getDeliveryStats(firstProjectId, { contributor_id: contributorId }),
    enabled: !!firstProjectId,
  });

  const { data: workItemsData, isLoading: wiLoading } = useQuery({
    queryKey: ["delivery", firstProjectId, "workItems", { assignee_id: contributorId, state: stateFilter, page }],
    queryFn: () => api.listWorkItems(firstProjectId, {
      assignee_id: contributorId,
      state: stateFilter || undefined,
      page,
      page_size: pageSize,
    }),
    enabled: !!firstProjectId,
  });

  const totalPages = workItemsData ? Math.ceil(workItemsData.total / pageSize) : 0;

  if (!firstProjectId) {
    return <p className="text-muted-foreground">No project associated — delivery data unavailable.</p>;
  }

  return (
    <div className="space-y-6">
      {stats && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard title="Items Assigned" value={stats.total_work_items} tooltip="Total work items assigned to this contributor" />
            <StatCard title="Open Items" value={stats.open_items} tooltip="Currently active/new items" />
            <StatCard title="Completed" value={stats.completed_items} tooltip="Resolved or closed items" />
            <StatCard
              title="Story Points Delivered"
              value={stats.completed_story_points}
              subtitle={`of ${stats.total_story_points} total`}
              tooltip="Story points on resolved items"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <StatCard title="Avg Cycle Time" value={`${stats.avg_cycle_time_hours}h`} subtitle="Activated → Resolved" tooltip="Median hours from active to resolved for this contributor's items" />
            <StatCard title="Avg Lead Time" value={`${stats.avg_lead_time_hours}h`} subtitle="Created → Closed" tooltip="Median hours from creation to closure" />
          </div>
        </>
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Work Items</h3>
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
