"use client";

import { AlertCircle, CheckCircle2, HelpCircle, MinusCircle, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useBacklogTrustedScorecard } from "@/hooks/use-delivery";
import type { TrafficLight, TrustedBacklogPillar } from "@/lib/types";
import { cn } from "@/lib/utils";

const LIGHT_STYLES: Record<TrafficLight, { bg: string; fg: string; icon: typeof CheckCircle2 }> = {
  green: { bg: "bg-emerald-500/10", fg: "text-emerald-700 dark:text-emerald-400", icon: CheckCircle2 },
  yellow: { bg: "bg-amber-500/10", fg: "text-amber-700 dark:text-amber-400", icon: AlertCircle },
  red: { bg: "bg-red-500/10", fg: "text-red-700 dark:text-red-400", icon: AlertCircle },
  unknown: { bg: "bg-muted", fg: "text-muted-foreground", icon: HelpCircle },
};

function PillarRow({ pillar }: { pillar: TrustedBacklogPillar }) {
  const style = LIGHT_STYLES[pillar.traffic_light] ?? LIGHT_STYLES.unknown;
  const Icon = pillar.measurable ? style.icon : MinusCircle;
  const detailKeys = Object.keys(pillar.details || {}).slice(0, 4);
  return (
    <div className={cn("rounded-lg border px-3 py-2", style.bg)}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className={cn("h-4 w-4 shrink-0", style.fg)} />
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{pillar.label}</div>
            {!pillar.measurable && (
              <div className="text-xs text-muted-foreground">Not measurable from data</div>
            )}
          </div>
        </div>
        {pillar.measurable && (
          <Badge variant="outline" className={cn("text-[10px] shrink-0", style.fg)}>
            {pillar.score.toFixed(0)}
          </Badge>
        )}
      </div>
      {detailKeys.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
          {detailKeys.map((k) => {
            const v = (pillar.details as Record<string, unknown>)[k];
            if (v == null || typeof v === "object") return null;
            return (
              <span key={k}>
                <span className="opacity-70">{k}:</span> <span className="font-mono">{String(v)}</span>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function TrustedBacklogCard({
  projectId,
  teamId,
  title = "Trusted Backlog Scorecard",
}: {
  projectId: string;
  teamId?: string;
  title?: string;
}) {
  const { data, isLoading } = useBacklogTrustedScorecard(projectId, teamId ? { team_id: teamId } : undefined);

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
          <p className="text-sm text-muted-foreground">No scorecard available.</p>
        </CardContent>
      </Card>
    );
  }

  const overallStyle = LIGHT_STYLES[data.overall_traffic_light] ?? LIGHT_STYLES.unknown;
  const OverallIcon = overallStyle.icon;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
        <div className={cn("flex items-center gap-2 rounded-full px-2 py-1 text-xs font-medium", overallStyle.bg, overallStyle.fg)}>
          <OverallIcon className="h-3.5 w-3.5" />
          {data.overall_traffic_light.toUpperCase()} · {data.overall_score.toFixed(0)}
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.pillars.map((p) => (
          <PillarRow key={p.key} pillar={p} />
        ))}
      </CardContent>
    </Card>
  );
}
