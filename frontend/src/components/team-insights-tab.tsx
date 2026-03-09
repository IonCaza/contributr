"use client";

import { useState, useCallback, useEffect } from "react";
import {
  AlertTriangle, AlertCircle, Info, CheckCircle2, Play, Loader2,
  ChevronDown, ChevronRight, X, Clock, TrendingUp,
  Gauge, Users, Briefcase, Settings, BookOpen,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useQueryClient } from "@tanstack/react-query";
import {
  useTeamInsightFindings,
  useTeamInsightsSummary,
  useTeamInsightRuns,
  useTriggerTeamInsightRun,
  useDismissTeamInsightFinding,
} from "@/hooks/use-team-insights";
import { queryKeys } from "@/lib/query-keys";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import { formatRelativeTime } from "@/components/insight-finding-card";
import { InsightRunHistory } from "@/components/insight-run-history";
import { api } from "@/lib/api-client";
import type { TeamInsightFinding } from "@/lib/types";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "velocity", label: "Velocity" },
  { value: "collaboration", label: "Collaboration" },
  { value: "workload", label: "Workload" },
  { value: "process", label: "Process" },
  { value: "knowledge", label: "Knowledge" },
] as const;

const SEVERITIES = [
  { value: "", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "warning", label: "Warning" },
  { value: "info", label: "Info" },
] as const;

const SEVERITY_CONFIG: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  critical: { icon: AlertTriangle, color: "text-red-500", bg: "bg-red-500/10" },
  warning: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-500/10" },
  info: { icon: Info, color: "text-blue-500", bg: "bg-blue-500/10" },
};

const CATEGORY_CONFIG: Record<string, { icon: typeof Gauge; label: string }> = {
  velocity: { icon: Gauge, label: "Velocity" },
  collaboration: { icon: Users, label: "Collaboration" },
  workload: { icon: Briefcase, label: "Workload" },
  process: { icon: Settings, label: "Process" },
  knowledge: { icon: BookOpen, label: "Knowledge" },
};

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
              <p className="font-semibold text-lg">Team Health Score</p>
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
            <><Loader2 className="h-4 w-4 animate-spin mr-1" />Analyzing...</>
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
    { label: "Improved", value: summary.resolved_30d, icon: TrendingUp, color: "text-emerald-500" },
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

function FindingCard({
  finding,
  onDismiss,
}: {
  finding: TeamInsightFinding;
  onDismiss: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [showDismissConfirm, setShowDismissConfirm] = useState(false);
  const config = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.info;
  const Icon = config.icon;
  const catConfig = CATEGORY_CONFIG[finding.category];
  const CatIcon = catConfig?.icon;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="transition-colors hover:border-border">
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer py-3 px-4">
            <div className="flex items-center gap-3 w-full">
              <div className={`shrink-0 p-1.5 rounded-md ${config.bg}`}>
                <Icon className={`h-4 w-4 ${config.color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="text-[10px] uppercase tracking-wider gap-1">
                    {CatIcon && <CatIcon className="h-3 w-3" />}
                    {catConfig?.label ?? finding.category}
                  </Badge>
                  <CardTitle className="text-sm font-medium truncate">
                    {finding.title}
                  </CardTitle>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Detected {formatRelativeTime(finding.first_detected_at)}
                  {finding.first_detected_at !== finding.last_detected_at && (
                    <> &middot; Last seen {formatRelativeTime(finding.last_detected_at)}</>
                  )}
                </p>
              </div>
              <div className="shrink-0">
                {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="pt-0 pb-4 px-4 space-y-3 border-t">
            <div className="pt-3">
              <p className="text-sm leading-relaxed">{finding.description}</p>
            </div>

            {finding.recommendation && (
              <div className="rounded-md bg-muted/50 p-3">
                <p className="text-xs font-semibold mb-1">Recommendation</p>
                <p className="text-sm text-muted-foreground">{finding.recommendation}</p>
              </div>
            )}

            {finding.metric_data && Object.keys(finding.metric_data).length > 0 && (
              <MetricDataView data={finding.metric_data} />
            )}

            <div className="flex justify-end pt-1">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDismissConfirm(true);
                }}
              >
                <X className="h-3.5 w-3.5 mr-1" />
                Dismiss
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>

      <ConfirmDialog
        open={showDismissConfirm}
        onOpenChange={setShowDismissConfirm}
        title="Dismiss finding?"
        description="This finding will be hidden from the active list. It can still be seen by filtering for dismissed findings."
        onConfirm={() => onDismiss(finding.id)}
        confirmLabel="Dismiss"
        variant="default"
      />
    </Collapsible>
  );
}

function MetricDataView({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(
    ([, v]) => v !== null && v !== undefined && !Array.isArray(v) && typeof v !== "object",
  );
  const listEntries = Object.entries(data).filter(
    ([, v]) => Array.isArray(v),
  );

  if (entries.length === 0 && listEntries.length === 0) return null;

  return (
    <div className="space-y-2">
      {entries.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {entries.map(([k, v]) => (
            <div key={k} className="rounded-md bg-muted/30 px-2.5 py-1.5">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{formatMetricKey(k)}</p>
              <p className="text-sm font-medium">{formatMetricValue(v)}</p>
            </div>
          ))}
        </div>
      )}
      {listEntries.map(([k, v]) => {
        const arr = v as unknown[];
        if (arr.length === 0) return null;
        return (
          <div key={k}>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">{formatMetricKey(k)}</p>
            <div className="space-y-1 max-h-32 overflow-y-auto text-xs text-muted-foreground">
              {arr.slice(0, 5).map((item, i) => (
                <div key={i} className="bg-muted/30 rounded px-2 py-1">
                  {typeof item === "object" ? JSON.stringify(item) : String(item)}
                </div>
              ))}
              {arr.length > 5 && <p className="text-muted-foreground/60">+{arr.length - 5} more</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatMetricKey(key: string): string {
  return key.replace(/_/g, " ").replace(/pct$/i, "%");
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
}

const getTeamLogUrl = (projectId: string, teamId: string) => (runId: string) =>
  `${api.getApiBase()}/projects/${projectId}/teams/${teamId}/insights/runs/${runId}/logs`;

export function TeamInsightsTab({ projectId, teamId }: { projectId: string; teamId: string }) {
  const qc = useQueryClient();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const filters = {
    ...(categoryFilter && { category: categoryFilter }),
    ...(severityFilter && { severity: severityFilter }),
  };

  const { data: summary } = useTeamInsightsSummary(projectId, teamId);
  const { data: findings, isLoading } = useTeamInsightFindings(projectId, teamId, filters);
  const { data: runs, refetch: refetchRuns } = useTeamInsightRuns(projectId, teamId);
  const triggerRun = useTriggerTeamInsightRun(projectId, teamId);
  const dismissFinding = useDismissTeamInsightFinding(projectId, teamId);

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
    ? `${api.getApiBase()}/projects/${projectId}/teams/${teamId}/insights/runs/${activeRunId}/logs`
    : null;

  const handleLogsDone = useCallback(() => {
    setActiveRunId(null);
    refetchRuns();
    qc.invalidateQueries({ queryKey: queryKeys.teamInsights.findings(projectId, teamId) });
    qc.invalidateQueries({ queryKey: queryKeys.teamInsights.summary(projectId, teamId) });
  }, [projectId, teamId, qc, refetchRuns]);

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
                ? "Great teamwork! No issues detected right now."
                : "Run an analysis to generate team insights."}
            </p>
          </CardContent>
        </Card>
      )}

      <InsightRunHistory runs={runs} getLogUrl={getTeamLogUrl(projectId, teamId)} />
    </div>
  );
}
