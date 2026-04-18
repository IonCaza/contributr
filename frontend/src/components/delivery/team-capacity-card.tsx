"use client";

import { Activity, AlertTriangle, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useTeamCapacityVsLoad } from "@/hooks/use-delivery";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, { bg: string; fg: string; label: string; icon: typeof TrendingUp }> = {
  overloaded: { bg: "bg-red-500/10", fg: "text-red-700 dark:text-red-400", label: "Overloaded", icon: AlertTriangle },
  "over-capacity": { bg: "bg-amber-500/10", fg: "text-amber-700 dark:text-amber-400", label: "Over capacity", icon: TrendingUp },
  balanced: { bg: "bg-emerald-500/10", fg: "text-emerald-700 dark:text-emerald-400", label: "Balanced", icon: Activity },
  "under-loaded": { bg: "bg-blue-500/10", fg: "text-blue-700 dark:text-blue-400", label: "Under-loaded", icon: TrendingDown },
  unknown: { bg: "bg-muted", fg: "text-muted-foreground", label: "Unknown", icon: Minus },
};

export function TeamCapacityCard({
  projectId,
  teamId,
  iterationId,
  title = "Capacity vs. Load",
}: {
  projectId: string;
  teamId: string;
  iterationId?: string;
  title?: string;
}) {
  const { data, isLoading } = useTeamCapacityVsLoad(projectId, teamId, iterationId ? { iteration_id: iterationId } : undefined);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading…</p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No data available.</p>
        </CardContent>
      </Card>
    );
  }

  const status = data.load_status ?? "unknown";
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.unknown;
  const StatusIcon = style.icon;
  const pct = data.avg_capacity_points > 0
    ? Math.min(200, Math.round((data.planned_points / data.avg_capacity_points) * 100))
    : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {data.target_iteration && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {data.target_iteration.name ?? data.target_iteration.path}
              </p>
            )}
          </div>
          <div className={cn("flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium", style.bg, style.fg)}>
            <StatusIcon className="h-3.5 w-3.5" />
            {style.label}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <div className="text-xs text-muted-foreground">Capacity (avg of {data.rolling_window})</div>
            <div className="text-xl font-semibold tabular-nums">{data.avg_capacity_points.toFixed(1)} SP</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Planned</div>
            <div className="text-xl font-semibold tabular-nums">{data.planned_points.toFixed(1)} SP</div>
            {typeof data.planned_items === "number" && (
              <div className="text-[11px] text-muted-foreground">{data.planned_items} items</div>
            )}
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Ready</div>
            <div className="text-xl font-semibold tabular-nums">{data.ready_points.toFixed(1)} SP</div>
          </div>
        </div>

        {pct !== null && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Load</span>
              <span>
                {data.load_ratio !== null ? `${(data.load_ratio * 100).toFixed(0)}%` : "—"}
                {typeof data.unestimated_items === "number" && data.unestimated_items > 0 && (
                  <span className="ml-2">· {data.unestimated_items} unestimated</span>
                )}
              </span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  status === "overloaded" && "bg-red-500",
                  status === "over-capacity" && "bg-amber-500",
                  status === "balanced" && "bg-emerald-500",
                  status === "under-loaded" && "bg-blue-500",
                  status === "unknown" && "bg-muted-foreground/40",
                )}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
          </div>
        )}

        {data.capacity_history.length > 0 && (
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            {data.capacity_history.slice(0, 6).map((h) => (
              <Badge key={h.iteration_id} variant="secondary" className="text-[10px] font-mono">
                {h.iteration_name ?? "—"}: {h.completed_points.toFixed(0)} SP
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
