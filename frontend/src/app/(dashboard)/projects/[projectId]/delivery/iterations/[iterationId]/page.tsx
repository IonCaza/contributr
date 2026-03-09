"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/stat-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { SprintBurndownChart } from "@/components/charts/sprint-burndown-chart";
import { useSprintDetail } from "@/hooks/use-delivery";

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
  if (lower.includes("active") || lower.includes("progress"))
    cls = "bg-blue-500/10 text-blue-700 dark:text-blue-400";
  else if (
    lower.includes("resolved") ||
    lower.includes("done") ||
    lower.includes("completed")
  )
    cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed"))
    cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new"))
    cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return (
    <Badge variant="secondary" className={`text-[10px] ${cls}`}>
      {state}
    </Badge>
  );
}

export default function SprintDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; iterationId: string }>;
}) {
  const { projectId, iterationId } = use(params);
  const { data: sprint, isLoading } = useSprintDetail(projectId, iterationId);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        Loading sprint...
      </div>
    );
  }

  if (!sprint) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/projects/${projectId}/delivery`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Link>
        </Button>
        <p className="text-muted-foreground">Sprint not found.</p>
      </div>
    );
  }

  const stats = sprint.stats;
  const pct =
    stats && stats.total_items > 0
      ? Math.round((stats.completed_items / stats.total_items) * 100)
      : 0;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href={`/projects/${projectId}/delivery`}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Project
        </Link>
      </Button>

      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">{sprint.name}</h1>
        {(sprint.start_date || sprint.end_date) && (
          <p className="text-sm text-muted-foreground">
            {sprint.start_date ?? "?"} → {sprint.end_date ?? "?"}
          </p>
        )}
        <div className="flex items-center gap-3">
          <div className="h-2.5 flex-1 max-w-sm rounded-full bg-muted">
            <div
              className="h-2.5 rounded-full bg-primary transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-sm font-medium">{pct}%</span>
        </div>
      </div>

      {/* Stat cards */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard title="Total Items" value={stats.total_items} tooltip="Total work items assigned to this sprint" />
          <StatCard title="Completed" value={stats.completed_items} tooltip="Work items that have been resolved or closed" />
          <StatCard title="Total Points" value={stats.total_points} tooltip="Sum of story points across all sprint items" />
          <StatCard title="Completed Points" value={stats.completed_points} tooltip="Story points on resolved/closed items" />
        </div>
      )}

      {/* Burndown chart */}
      {sprint.burndown.length > 0 && (
        <SprintBurndownChart data={sprint.burndown} />
      )}

      {/* Work Items table */}
      {sprint.work_items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Work Items ({sprint.work_items.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">Points</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sprint.work_items.map((wi) => (
                  <TableRow
                    key={wi.id}
                    className="cursor-pointer hover:bg-muted/50"
                  >
                    <TableCell className="text-xs text-muted-foreground">
                      #{wi.platform_work_item_id}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={`text-[10px] ${TYPE_COLORS[wi.work_item_type] || ""}`}
                      >
                        {TYPE_LABELS[wi.work_item_type] || wi.work_item_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${wi.id}`}
                        className="font-medium hover:underline"
                      >
                        {wi.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StateTag state={wi.state} />
                    </TableCell>
                    <TableCell className="text-right">
                      {wi.story_points ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Contributors breakdown */}
      {sprint.contributors.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contributors</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Completed</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="text-right">Completion %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sprint.contributors.map((c) => {
                  const compPct =
                    c.total > 0
                      ? Math.round((c.completed / c.total) * 100)
                      : 0;
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">
                        {c.name ?? "Unknown"}
                      </TableCell>
                      <TableCell className="text-right">
                        {c.completed}
                      </TableCell>
                      <TableCell className="text-right">{c.total}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-1.5 w-16 rounded-full bg-muted">
                            <div
                              className="h-1.5 rounded-full bg-primary"
                              style={{ width: `${compPct}%` }}
                            />
                          </div>
                          <span className="text-xs w-8 text-right">
                            {compPct}%
                          </span>
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
    </div>
  );
}
