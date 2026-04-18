"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Repeat, Shuffle } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/stat-card";
import {
  useCarryoverSummary, useCarryoverBySprint, useCarryoverItems,
} from "@/hooks/use-delivery";
import type { CarryoverBySprint } from "@/lib/types";

export function CarryoverTab({
  projectId,
  teamId,
  fromDate,
  toDate,
}: {
  projectId: string;
  teamId?: string;
  fromDate?: string;
  toDate?: string;
}) {
  const params = { team_id: teamId, from_date: fromDate, to_date: toDate };
  const { data: summary, isLoading: summaryLoading } = useCarryoverSummary(projectId, params);
  const { data: sprints } = useCarryoverBySprint(projectId, { team_id: teamId, limit: 12 });
  const { data: itemsPage } = useCarryoverItems(projectId, {
    team_id: teamId,
    min_moves: 2,
    from_date: fromDate,
    to_date: toDate,
    limit: 25,
  });

  const chartData = useMemo(() => {
    if (!sprints) return [] as CarryoverBySprint[];
    return [...sprints].reverse();
  }, [sprints]);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Carry-over rate"
          value={summary ? `${summary.carryover_rate_pct}%` : summaryLoading ? "…" : "—"}
          subtitle={summary ? `${summary.carried_work_items} of ${summary.total_work_items} items moved` : undefined}
          tooltip="% of work items that had their iteration path changed at least once in the window"
        />
        <StatCard
          title="Total moves"
          value={summary?.total_moves ?? (summaryLoading ? "…" : "—")}
          subtitle="Iteration-path changes recorded"
        />
        <StatCard
          title="Avg moves / moved item"
          value={summary ? summary.avg_moves_per_item.toFixed(2) : (summaryLoading ? "…" : "—")}
          subtitle="Higher = more churn"
        />
        <StatCard
          title="Items with 2+ moves"
          value={itemsPage?.total ?? (summaryLoading ? "…" : "—")}
          subtitle="Repeatedly rescheduled"
        />
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Repeat className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Per-sprint carry-over</CardTitle>
          </div>
          <p className="text-xs text-muted-foreground">
            Items moved <b>out</b> (rescheduled away) and moved <b>in</b> (arrived from another sprint) during each
            sprint&apos;s active window.
          </p>
        </CardHeader>
        <CardContent>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ left: 8, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="iteration_name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="moved_out" name="Moved out" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="moved_in" name="Moved in" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground">No sprint carry-over data available.</p>
          )}
        </CardContent>
      </Card>

      {sprints && sprints.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Sprint breakdown</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sprint</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Completed</TableHead>
                  <TableHead className="text-right">Moved out</TableHead>
                  <TableHead className="text-right">Moved in</TableHead>
                  <TableHead className="text-right">Carry-over %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sprints.map((s) => (
                  <TableRow key={s.iteration_id}>
                    <TableCell className="font-medium">{s.iteration_name ?? s.iteration_path}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.total_items}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.completed_items}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.moved_out}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.moved_in}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      <Badge
                        variant={s.carryover_rate_pct >= 25 ? "destructive" : s.carryover_rate_pct >= 10 ? "outline" : "secondary"}
                        className="text-[10px]"
                      >
                        {s.carryover_rate_pct}%
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Shuffle className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Most-moved items</CardTitle>
          </div>
          <p className="text-xs text-muted-foreground">
            Items rescheduled two or more times. Frequent reshufflers often indicate scope or priority drift.
          </p>
        </CardHeader>
        <CardContent className="p-0">
          {itemsPage && itemsPage.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">ID</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead className="text-right">SP</TableHead>
                  <TableHead className="text-right">Moves</TableHead>
                  <TableHead>Last moved</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {itemsPage.items.map((it) => (
                  <TableRow key={it.work_item_id}>
                    <TableCell className="font-mono text-xs">
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${it.work_item_id}`}
                        className="hover:underline text-primary"
                      >
                        #{it.platform_work_item_id}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[320px] truncate">
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${it.work_item_id}`}
                        className="hover:underline"
                      >
                        {it.title ?? "—"}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">{it.work_item_type}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{it.state}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{it.assignee ?? "Unassigned"}</TableCell>
                    <TableCell className="text-right tabular-nums">{it.story_points ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      <Badge variant="destructive" className="text-[10px]">{it.move_count}×</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {it.last_moved_at ? new Date(it.last_moved_at).toLocaleDateString() : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">No items with two or more moves in this window.</p>
          )}
        </CardContent>
      </Card>

      {summary && summary.top_offenders.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Top offenders (all time)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {summary.top_offenders.slice(0, 10).map((o) => (
                <div key={o.work_item_id} className="flex items-center gap-3 text-sm">
                  <Link
                    href={`/projects/${projectId}/delivery/work-items/${o.work_item_id}`}
                    className="font-mono text-xs text-primary hover:underline w-16 shrink-0"
                  >
                    #{o.platform_work_item_id}
                  </Link>
                  <span className="flex-1 truncate">{o.title ?? "—"}</span>
                  <Badge variant="outline" className="text-[10px]">{o.work_item_type}</Badge>
                  <span className="text-xs text-muted-foreground w-20 text-right">{o.state}</span>
                  <Badge variant="destructive" className="text-[10px] w-12 justify-center">{o.move_count}×</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
