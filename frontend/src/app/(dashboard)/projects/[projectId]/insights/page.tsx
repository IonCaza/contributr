"use client";

import { use, useState, useCallback } from "react";
import { useActiveRunTracking } from "@/hooks/use-active-run-tracking";
import {
  AlertTriangle, AlertCircle, Info, CheckCircle2, Play, Loader2, TrendingUp,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useQueryClient } from "@tanstack/react-query";
import {
  useInsightFindings,
  useInsightsSummary,
  useInsightRuns,
  useTriggerInsightRun,
  useDismissInsightFinding,
} from "@/hooks/use-insights";
import { queryKeys } from "@/lib/query-keys";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import { FindingCard, formatRelativeTime } from "@/components/insight-finding-card";
import { InsightRunHistory } from "@/components/insight-run-history";
import { api } from "@/lib/api-client";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "process", label: "Process" },
  { value: "delivery", label: "Delivery" },
  { value: "team_balance", label: "Team" },
  { value: "code_quality", label: "Code Quality" },
  { value: "intersection", label: "Intersection" },
] as const;

const SEVERITIES = [
  { value: "", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "warning", label: "Warning" },
  { value: "info", label: "Info" },
] as const;

const CRITICAL_PENALTY = 15;
const WARNING_PENALTY = 5;
const INFO_PENALTY = 1;

function HealthScoreBanner({
  summary,
  isLoading,
  lastRun,
  onRunAnalysis,
  isRunning,
}: {
  summary: { total_active: number; critical: number; warning: number; info: number; resolved_30d: number } | undefined;
  isLoading: boolean;
  lastRun: { started_at: string; status: string } | undefined;
  onRunAnalysis: () => void;
  isRunning: boolean;
}) {
  const [sheetOpen, setSheetOpen] = useState(false);

  const score = summary
    ? Math.max(0, 100 - (summary.critical * CRITICAL_PENALTY) - (summary.warning * WARNING_PENALTY) - (summary.info * INFO_PENALTY))
    : null;

  const deductions = summary
    ? {
        critical: summary.critical * CRITICAL_PENALTY,
        warning: summary.warning * WARNING_PENALTY,
        info: summary.info * INFO_PENALTY,
        total: (summary.critical * CRITICAL_PENALTY) + (summary.warning * WARNING_PENALTY) + (summary.info * INFO_PENALTY),
      }
    : null;

  const scoreColor = score === null
    ? "bg-muted"
    : score >= 80
      ? "bg-emerald-500"
      : score >= 50
        ? "bg-amber-500"
        : "bg-red-500";

  const lastRunLabel = lastRun
    ? `Last analyzed: ${formatRelativeTime(lastRun.started_at)}`
    : "No analysis runs yet";

  return (
    <>
      <Card>
        <CardContent className="flex items-center justify-between py-4 px-6">
          <div className="flex items-center gap-4">
            {isLoading && !summary ? (
              <>
                <Skeleton className="h-12 w-12 rounded-full" />
                <div className="space-y-1.5">
                  <Skeleton className="h-5 w-28" />
                  <Skeleton className="h-4 w-36" />
                </div>
                <Skeleton className="hidden sm:block h-2 w-48 rounded-full" />
              </>
            ) : (
              <>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        className="flex items-center gap-3 cursor-pointer select-none rounded-lg p-1 -m-1 hover:bg-muted/50 transition-colors"
                        onDoubleClick={() => setSheetOpen(true)}
                      >
                        <div className={`h-12 w-12 rounded-full ${scoreColor} flex items-center justify-center`}>
                          <span className="text-white font-bold text-lg">{score ?? "?"}</span>
                        </div>
                        <div>
                          <p className="font-semibold text-lg">Health Score</p>
                          <p className="text-sm text-muted-foreground">{lastRunLabel}</p>
                        </div>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-64">
                      <p>Double-click to see how the Health Score is calculated</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {score !== null && (
                  <div className="hidden sm:flex items-center gap-1 ml-4">
                    <div className="h-2 w-48 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${scoreColor}`}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                  </div>
                )}
              </>
            )}
        </div>
        <Button onClick={onRunAnalysis} disabled={isRunning} size="sm">
          {isRunning ? (
            <><Loader2 className="h-4 w-4 animate-spin mr-1" />Running...</>
          ) : (
            <><Play className="h-4 w-4 mr-1" />Run Analysis</>
          )}
        </Button>
      </CardContent>
    </Card>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>How Health Score is Calculated</SheetTitle>
            <SheetDescription>
              The Health Score starts at 100 and is reduced by active findings based on severity.
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-6 px-4 pb-6">
            <div className="rounded-lg border bg-muted/30 p-3 font-mono text-sm">
              <p className="text-muted-foreground mb-1">Formula:</p>
              <p>100 − (critical × 15) − (warning × 5) − (info × 1)</p>
              <p className="text-xs text-muted-foreground mt-2">Minimum score is 0</p>
            </div>

            {summary && deductions && (
              <div>
                <p className="text-sm font-medium mb-2">Current breakdown</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Severity</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                      <TableHead className="text-right">Points each</TableHead>
                      <TableHead className="text-right">Deduction</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell className="flex items-center gap-1.5">
                        <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                        Critical
                      </TableCell>
                      <TableCell className="text-right">{summary.critical}</TableCell>
                      <TableCell className="text-right">−15</TableCell>
                      <TableCell className="text-right text-red-600">−{deductions.critical}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="flex items-center gap-1.5">
                        <AlertCircle className="h-3.5 w-3.5 text-amber-500" />
                        Warning
                      </TableCell>
                      <TableCell className="text-right">{summary.warning}</TableCell>
                      <TableCell className="text-right">−5</TableCell>
                      <TableCell className="text-right text-amber-600">−{deductions.warning}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="flex items-center gap-1.5">
                        <Info className="h-3.5 w-3.5 text-blue-500" />
                        Info
                      </TableCell>
                      <TableCell className="text-right">{summary.info}</TableCell>
                      <TableCell className="text-right">−1</TableCell>
                      <TableCell className="text-right text-blue-600">−{deductions.info}</TableCell>
                    </TableRow>
                    <TableRow className="font-medium">
                      <TableCell colSpan={3}>Total deduction</TableCell>
                      <TableCell className="text-right">−{deductions.total}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
                <p className="text-sm text-muted-foreground mt-3">
                  <strong>Score:</strong> 100 − {deductions.total} = <strong>{score}</strong>
                </p>
              </div>
            )}

            {!summary && (
              <p className="text-sm text-muted-foreground">Run an analysis to see your current breakdown.</p>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

function SummaryCards({
  summary,
  isLoading,
}: {
  summary: { total_active: number; critical: number; warning: number; info: number; resolved_30d: number } | undefined;
  isLoading: boolean;
}) {
  if (!summary && !isLoading) return null;

  if (!summary) {
    return (
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="flex items-center gap-3 py-4 px-4">
              <Skeleton className="h-8 w-8 rounded-md" />
              <div className="space-y-1.5">
                <Skeleton className="h-7 w-10" />
                <Skeleton className="h-3 w-16" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    { label: "Critical", value: summary.critical, icon: AlertTriangle, color: "text-red-500" },
    { label: "Warnings", value: summary.warning, icon: AlertCircle, color: "text-amber-500" },
    { label: "Improvements", value: summary.resolved_30d, icon: TrendingUp, color: "text-emerald-500" },
    { label: "Active Insights", value: summary.total_active, icon: Info, color: "text-blue-500" },
  ];

  return (
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardContent className="flex items-center gap-3 py-4 px-4">
            <c.icon className={`h-8 w-8 ${c.color}`} />
            <div>
              <p className="text-2xl font-bold">{c.value}</p>
              <p className="text-xs text-muted-foreground">{c.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}


const getProjectLogUrl = (projectId: string) => (runId: string) =>
  `${api.getApiBase()}/projects/${projectId}/insights/runs/${runId}/logs`;

export default function InsightsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const qc = useQueryClient();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const filters = {
    ...(categoryFilter && { category: categoryFilter }),
    ...(severityFilter && { severity: severityFilter }),
  };

  const { data: summary, isLoading: summaryLoading } = useInsightsSummary(projectId);
  const { data: findings, isLoading: findingsLoading } = useInsightFindings(projectId, filters);
  const { data: runs, refetch: refetchRuns } = useInsightRuns(projectId);
  const triggerRun = useTriggerInsightRun(projectId);
  const dismissFinding = useDismissInsightFinding(projectId);

  const lastRun = runs?.[0];
  const isRunning = lastRun?.status === "running" || triggerRun.isPending;
  const { activeRunId, startTracking, stopTracking } = useActiveRunTracking(lastRun);

  useRegisterUIContext("insights", {
    summary,
    findingsCount: findings?.length ?? 0,
    filters: { category: categoryFilter, severity: severityFilter },
  });

  const handleTriggerRun = useCallback(() => {
    triggerRun.mutate(undefined, {
      onSuccess: (run) => startTracking(run.id),
    });
  }, [triggerRun, startTracking]);

  const logUrl = activeRunId
    ? `${api.getApiBase()}/projects/${projectId}/insights/runs/${activeRunId}/logs`
    : null;

  const handleLogsDone = useCallback(() => {
    stopTracking();
    refetchRuns();
    qc.invalidateQueries({ queryKey: ["insights", projectId, "findings"] });
    qc.invalidateQueries({ queryKey: queryKeys.insights.summary(projectId) });
  }, [stopTracking, projectId, qc, refetchRuns]);

  return (
    <div className="space-y-6">
      <HealthScoreBanner
        summary={summary}
        isLoading={summaryLoading}
        lastRun={lastRun}
        onRunAnalysis={handleTriggerRun}
        isRunning={isRunning}
      />

      {logUrl && isRunning && (
        <SyncLogViewer logUrl={logUrl} compact title="Analysis Logs" onDone={handleLogsDone} />
      )}

      <SummaryCards summary={summary} isLoading={summaryLoading} />

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              onClick={() => setCategoryFilter(c.value)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                categoryFilter === c.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
          {SEVERITIES.map((s) => (
            <button
              key={s.value}
              onClick={() => setSeverityFilter(s.value)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                severityFilter === s.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Findings list */}
      {findingsLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="flex items-start gap-3 py-4 px-4">
                <Skeleton className="h-8 w-8 rounded-md mt-0.5" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : findings && findings.length > 0 ? (
        <div className="space-y-3">
          {findings.map((f) => (
            <FindingCard
              key={f.id}
              finding={f}
              onDismiss={(id) => dismissFinding.mutate(id)}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <CheckCircle2 className="h-10 w-10 mb-2 text-emerald-500" />
            <p className="font-medium">No active findings</p>
            <p className="text-sm mt-1">
              {runs?.length
                ? "Great job! All insights have been resolved or dismissed."
                : "Run an analysis to generate insights for this project."}
            </p>
          </CardContent>
        </Card>
      )}

      <InsightRunHistory runs={runs} getLogUrl={getProjectLogUrl(projectId)} />
    </div>
  );
}
