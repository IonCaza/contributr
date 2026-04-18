"use client";

import Link from "next/link";
import { Clock, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";
import { useLongRunningStories } from "@/hooks/use-delivery";
import { cn } from "@/lib/utils";

const SIGNAL_STYLES: Record<string, string> = {
  stalled: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  no_updates: "bg-red-500/10 text-red-700 dark:text-red-400",
  iteration_hopping: "bg-purple-500/10 text-purple-700 dark:text-purple-400",
  reassigned_often: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-400",
  oversized: "bg-orange-500/10 text-orange-700 dark:text-orange-400",
  state_loop: "bg-rose-500/10 text-rose-700 dark:text-rose-400",
  unestimated: "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
  unassigned: "bg-red-500/10 text-red-700 dark:text-red-400",
};

function signalLabel(s: string) {
  return s.replace(/_/g, " ");
}

export function LongRunningStoriesCard({
  projectId,
  teamId,
  title = "Long-running stories",
  limit = 25,
}: {
  projectId: string;
  teamId?: string;
  title?: string;
  limit?: number;
}) {
  const { data, isLoading } = useLongRunningStories(projectId, { team_id: teamId, limit });

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">{title}</CardTitle>
            </div>
            {data && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {data.count} items · threshold {data.threshold_days}d
              </p>
            )}
          </div>
          {data && data.count > 0 && (
            <Badge variant="destructive" className="text-[10px]">
              <AlertCircle className="h-3 w-3 mr-1" /> {data.count} flagged
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <p className="px-6 py-4 text-sm text-muted-foreground">Loading…</p>
        ) : !data || data.items.length === 0 ? (
          <p className="px-6 py-4 text-sm text-muted-foreground">
            No items exceeding the {data?.threshold_days ?? 14}-day threshold.
          </p>
        ) : (
          <TooltipProvider delayDuration={200}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">ID</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead className="text-right">Age (d)</TableHead>
                  <TableHead className="text-right">Idle (d)</TableHead>
                  <TableHead className="text-right">Moves</TableHead>
                  <TableHead className="text-right">SP</TableHead>
                  <TableHead>Why</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((it) => (
                  <TableRow key={it.work_item_id}>
                    <TableCell className="font-mono text-xs">
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${it.work_item_id}`}
                        className="hover:underline text-primary"
                      >
                        #{it.platform_work_item_id}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[280px]">
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${it.work_item_id}`}
                        className="hover:underline"
                      >
                        <div className="truncate">{it.title ?? "—"}</div>
                        <div className="text-[11px] text-muted-foreground">{it.state}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {it.assigned_to_name ?? "Unassigned"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <Badge
                        variant={it.days_active >= 30 ? "destructive" : "outline"}
                        className="text-[10px]"
                      >
                        {it.days_active}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {it.days_since_update}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {it.iteration_moves > 0 ? (
                        <Badge variant="secondary" className="text-[10px]">{it.iteration_moves}×</Badge>
                      ) : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {it.story_points ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex flex-wrap gap-1 cursor-help">
                            {it.signals.slice(0, 3).map((s) => (
                              <span
                                key={s}
                                className={cn(
                                  "text-[10px] rounded px-1.5 py-0.5 font-medium",
                                  SIGNAL_STYLES[s] ?? "bg-muted text-muted-foreground",
                                )}
                              >
                                {signalLabel(s)}
                              </span>
                            ))}
                            {it.signals.length > 3 && (
                              <span className="text-[10px] text-muted-foreground">+{it.signals.length - 3}</span>
                            )}
                            {it.signals.length === 0 && (
                              <span className="text-[10px] text-muted-foreground italic">on-track?</span>
                            )}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="left" className="max-w-xs text-xs">
                          {it.summary}
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TooltipProvider>
        )}
      </CardContent>
    </Card>
  );
}
