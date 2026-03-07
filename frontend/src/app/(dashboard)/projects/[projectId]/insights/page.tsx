"use client";

import { use, useState, useCallback, useEffect } from "react";
import {
  AlertTriangle, AlertCircle, Info, CheckCircle2, Play, Loader2, Clock, TrendingUp,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  useInsightFindings,
  useInsightsSummary,
  useInsightRuns,
  useTriggerInsightRun,
  useDismissInsightFinding,
} from "@/hooks/use-insights";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import { FindingCard, formatRelativeTime } from "@/components/insight-finding-card";
import { FindingsOverTimeChart } from "@/components/charts/findings-over-time-chart";
import { api } from "@/lib/api-client";

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

function HealthScoreBanner({
  summary,
  lastRun,
  onRunAnalysis,
  isRunning,
}: {
  summary: { total_active: number; critical: number; warning: number; info: number; resolved_30d: number } | undefined;
  lastRun: { started_at: string; status: string } | undefined;
  onRunAnalysis: () => void;
  isRunning: boolean;
}) {
  const score = summary
    ? Math.max(0, 100 - (summary.critical * 15) - (summary.warning * 5) - (summary.info * 1))
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
    <Card>
      <CardContent className="flex items-center justify-between py-4 px-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className={`h-12 w-12 rounded-full ${scoreColor} flex items-center justify-center`}>
              <span className="text-white font-bold text-lg">{score ?? "?"}</span>
            </div>
            <div>
              <p className="font-semibold text-lg">Health Score</p>
              <p className="text-sm text-muted-foreground">{lastRunLabel}</p>
            </div>
          </div>
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
  );
}

function SummaryCards({
  summary,
}: {
  summary: { total_active: number; critical: number; warning: number; info: number; resolved_30d: number } | undefined;
}) {
  if (!summary) return null;

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


function RunHistory({ projectId }: { projectId: string }) {
  const { data: runs } = useInsightRuns(projectId);
  const [expanded, setExpanded] = useState(false);

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
            return (
              <div key={run.id} className="flex items-center gap-3 text-sm py-1">
                <StatusIcon className={`h-3.5 w-3.5 ${statusColor} ${run.status === "running" ? "animate-spin" : ""}`} />
                <span className="text-muted-foreground">{formatRelativeTime(run.started_at)}</span>
                <span className="text-muted-foreground">&middot;</span>
                <span>{run.findings_count} findings</span>
                {run.error_message && (
                  <span className="text-xs text-red-400 truncate max-w-48" title={run.error_message}>
                    {run.error_message}
                  </span>
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

export default function InsightsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const filters = {
    ...(categoryFilter && { category: categoryFilter }),
    ...(severityFilter && { severity: severityFilter }),
  };

  const { data: summary } = useInsightsSummary(projectId);
  const { data: findings, isLoading } = useInsightFindings(projectId, filters);
  const { data: runs, refetch: refetchRuns } = useInsightRuns(projectId);
  const triggerRun = useTriggerInsightRun(projectId);
  const dismissFinding = useDismissInsightFinding(projectId);

  const lastRun = runs?.[0];
  const isRunning = lastRun?.status === "running" || triggerRun.isPending;

  useEffect(() => {
    if (lastRun?.status === "running" && !activeRunId) {
      setActiveRunId(lastRun.id);
    }
  }, [lastRun, activeRunId]);

  const handleTriggerRun = useCallback(() => {
    triggerRun.mutate(undefined, {
      onSuccess: (run) => {
        setActiveRunId(run.id);
      },
    });
  }, [triggerRun]);

  const logUrl = activeRunId
    ? `${api.getApiBase()}/projects/${projectId}/insights/runs/${activeRunId}/logs`
    : null;

  const handleLogsDone = useCallback(() => {
    setActiveRunId(null);
    refetchRuns();
  }, [refetchRuns]);

  return (
    <div className="space-y-6">
      <HealthScoreBanner
        summary={summary}
        lastRun={lastRun}
        onRunAnalysis={handleTriggerRun}
        isRunning={isRunning}
      />

      {logUrl && isRunning && (
        <SyncLogViewer logUrl={logUrl} compact title="Analysis Logs" onDone={handleLogsDone} />
      )}

      <SummaryCards summary={summary} />

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
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
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

      <RunHistory projectId={projectId} />
    </div>
  );
}
