"use client";

import { useState } from "react";
import {
  AlertTriangle, CheckCircle2, Loader2, Terminal,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import { FindingsOverTimeChart } from "@/components/charts/findings-over-time-chart";
import { formatRelativeTime } from "@/components/insight-finding-card";

export interface InsightRunItem {
  id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  findings_count: number;
  error_message: string | null;
}

interface InsightRunHistoryProps {
  runs: InsightRunItem[] | undefined;
  getLogUrl: (runId: string) => string;
}

export function InsightRunHistory({ runs, getLogUrl }: InsightRunHistoryProps) {
  const [expanded, setExpanded] = useState(false);
  const [viewingLogRunId, setViewingLogRunId] = useState<string | null>(null);

  if (!runs || runs.length === 0) return null;

  const visible = expanded ? runs : runs.slice(0, 5);

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Analysis History</CardTitle>
          {runs.length > 5 && (
            <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
              {expanded ? "Show less" : `Show all (${runs.length})`}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0 px-4 pb-3">
        <div className="space-y-1.5">
          {visible.map((run) => {
            const statusColor =
              run.status === "completed" ? "text-emerald-500" :
              run.status === "failed" ? "text-red-500" :
              "text-amber-500";
            const StatusIcon =
              run.status === "completed" ? CheckCircle2 :
              run.status === "failed" ? AlertTriangle :
              Loader2;
            const isViewingLogs = viewingLogRunId === run.id;
            return (
              <div key={run.id}>
                <div className="flex items-center gap-3 text-sm py-1">
                  <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${statusColor} ${run.status === "running" ? "animate-spin" : ""}`} />
                  <span className="text-muted-foreground">{formatRelativeTime(run.started_at)}</span>
                  <span className="text-muted-foreground">&middot;</span>
                  <span>{run.findings_count} findings</span>
                  {run.error_message && (
                    <span className="text-xs text-red-400 truncate max-w-48" title={run.error_message}>
                      {run.error_message}
                    </span>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs gap-1 ml-auto shrink-0"
                    onClick={() => setViewingLogRunId(isViewingLogs ? null : run.id)}
                  >
                    <Terminal className="h-3 w-3" />
                    {isViewingLogs ? "Hide" : "Logs"}
                  </Button>
                </div>
                {isViewingLogs && (
                  <div className="mt-1 mb-2">
                    <SyncLogViewer logUrl={getLogUrl(run.id)} title="Analysis Logs" />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {runs.length >= 2 && (
          <FindingsOverTimeChart
            runs={runs.map((r) => ({
              id: r.id,
              started_at: r.started_at,
              findings_count: r.findings_count,
              status: r.status,
            }))}
          />
        )}
      </CardContent>
    </Card>
  );
}
