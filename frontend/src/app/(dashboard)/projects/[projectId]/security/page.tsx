"use client";

import { use, useState, useCallback, useEffect } from "react";
import {
  ShieldAlert, ShieldCheck, AlertTriangle, AlertCircle, ChevronDown, ChevronRight,
  Play, Loader2, CheckCircle2, Info, FileCode, Bug, TrendingDown, EyeOff,
  XCircle, ExternalLink, Download, Ban,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useQueryClient } from "@tanstack/react-query";
import {
  useProjectSastFindings,
  useProjectSastSummary,
  useProjectSastRuns,
} from "@/hooks/use-sast";
import { queryKeys } from "@/lib/query-keys";
import { api } from "@/lib/api-client";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import { FindingsOverTimeChart } from "@/components/charts/findings-over-time-chart";
import type { SastFinding, SastSummary, SastScanRun, Repository } from "@/lib/types";

const SEVERITIES = [
  { value: "", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: "info", label: "Info" },
] as const;

const STATUSES = [
  { value: "", label: "Open" },
  { value: "fixed", label: "Fixed" },
  { value: "dismissed", label: "Dismissed" },
  { value: "false_positive", label: "False Positive" },
] as const;

const SEVERITY_CONFIG: Record<string, { icon: typeof ShieldAlert; color: string; bg: string }> = {
  critical: { icon: ShieldAlert, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30" },
  high: { icon: AlertTriangle, color: "text-orange-500", bg: "bg-orange-50 dark:bg-orange-950/30" },
  medium: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-50 dark:bg-amber-950/30" },
  low: { icon: Info, color: "text-blue-500", bg: "bg-blue-50 dark:bg-blue-950/30" },
  info: { icon: Info, color: "text-slate-400", bg: "bg-slate-50 dark:bg-slate-950/30" },
};

function formatRelativeTime(dateStr: string | null) {
  if (!dateStr) return "N/A";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function SecurityScoreBanner({
  summary,
  isLoading,
  lastRun,
  repos,
  onScanRepo,
  scanningRepoId,
  projectId,
}: {
  summary: SastSummary | undefined;
  isLoading: boolean;
  lastRun: SastScanRun | undefined;
  repos: Repository[];
  onScanRepo: (repoId: string) => void;
  scanningRepoId: string | null;
  projectId: string;
}) {
  const score = summary
    ? Math.max(0, 100 - (summary.critical * 20) - (summary.high * 10) - (summary.medium * 3) - (summary.low * 1))
    : null;

  const scoreColor = score === null
    ? "bg-muted"
    : score >= 80
      ? "bg-emerald-500"
      : score >= 50
        ? "bg-amber-500"
        : "bg-red-500";

  const lastRunLabel = lastRun
    ? `Last scan: ${formatRelativeTime(lastRun.created_at)}`
    : "No scans yet";

  function handleReportDownload(format: string) {
    const token = api.getAuthToken();
    const baseUrl = api.getProjectSastReportUrl(projectId, format);
    const url = token ? `${baseUrl}&token=${encodeURIComponent(token)}` : baseUrl;
    window.open(url, "_blank");
  }

  return (
    <Card>
      <CardContent className="flex items-center justify-between py-4 px-6 gap-4">
        <div className="flex items-center gap-4">
          {isLoading && !summary ? (
            <>
              <Skeleton className="h-12 w-12 rounded-full" />
              <div className="space-y-1.5">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-24" />
              </div>
              <Skeleton className="hidden sm:block h-2 w-48 rounded-full" />
            </>
          ) : (
            <>
              <div className={`h-12 w-12 rounded-full ${scoreColor} flex items-center justify-center`}>
                <span className="text-white font-bold text-lg">{score ?? "?"}</span>
              </div>
              <div>
                <p className="font-semibold text-lg">Security Score</p>
                <p className="text-sm text-muted-foreground">{lastRunLabel}</p>
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
            </>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {repos.length > 1 && (
            <Button
              onClick={() => repos.forEach((r) => onScanRepo(r.id))}
              disabled={!!scanningRepoId}
              size="sm"
            >
              {scanningRepoId ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" />Scanning...</>
              ) : (
                <><Play className="h-4 w-4 mr-1" />Scan All</>
              )}
            </Button>
          )}
          {repos.length === 1 && (
            <Button
              onClick={() => onScanRepo(repos[0].id)}
              disabled={scanningRepoId === repos[0].id}
              size="sm"
            >
              {scanningRepoId === repos[0].id ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" />Scanning...</>
              ) : (
                <><Play className="h-4 w-4 mr-1" />Run Scan</>
              )}
            </Button>
          )}
          {repos.length === 0 && isLoading && (
            <Skeleton className="h-9 w-24 rounded-md" />
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-1" /> Report
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleReportDownload("json")}>
                Download JSON
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleReportDownload("csv")}>
                Download CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleReportDownload("pdf")}>
                Download PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
}

function SeveritySummaryCards({ summary, isLoading }: { summary: SastSummary | undefined; isLoading: boolean }) {
  if (!summary && !isLoading) return null;

  if (!summary) {
    return (
      <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="flex items-center gap-3 py-4 px-4">
              <Skeleton className="h-7 w-7 rounded-md" />
              <div className="space-y-1.5">
                <Skeleton className="h-7 w-10" />
                <Skeleton className="h-3 w-14" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    { label: "Critical", value: summary.critical, icon: ShieldAlert, color: "text-red-600" },
    { label: "High", value: summary.high, icon: AlertTriangle, color: "text-orange-500" },
    { label: "Medium", value: summary.medium, icon: AlertCircle, color: "text-amber-500" },
    { label: "Low", value: summary.low, icon: Info, color: "text-blue-500" },
    { label: "Fixed (30d)", value: summary.fixed_30d, icon: TrendingDown, color: "text-emerald-500" },
    { label: "Total Open", value: summary.total_open, icon: Bug, color: "text-slate-500" },
  ];

  return (
    <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardContent className="flex items-center gap-3 py-4 px-4">
            <c.icon className={`h-7 w-7 ${c.color}`} />
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

function SastFindingRow({
  finding,
  onDismiss,
  onFalsePositive,
  onIgnoreRule,
}: {
  finding: SastFinding;
  onDismiss: (id: string) => void;
  onFalsePositive: (id: string) => void;
  onIgnoreRule: (ruleId: string, repoId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  const SevIcon = config.icon;

  const ruleShort = finding.rule_id.split(".").slice(-2).join(".");

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className={`border-l-4 ${
        finding.severity === "critical" ? "border-l-red-500" :
        finding.severity === "high" ? "border-l-orange-500" :
        finding.severity === "medium" ? "border-l-amber-500" :
        finding.severity === "low" ? "border-l-blue-500" :
        "border-l-slate-300"
      }`}>
        <CollapsibleTrigger asChild>
          <CardContent className="flex items-start gap-3 py-3 px-4 cursor-pointer hover:bg-muted/30 transition-colors">
            <div className={`rounded-md p-1.5 mt-0.5 ${config.bg}`}>
              <SevIcon className={`h-4 w-4 ${config.color}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-sm">{finding.message}</span>
                <Badge variant="outline" className="text-xs font-mono">{ruleShort}</Badge>
                {finding.cwe_ids?.map((c) => (
                  <Badge key={c} variant="secondary" className="text-xs">{c}</Badge>
                ))}
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <FileCode className="h-3 w-3" />
                  {finding.file_path}:{finding.start_line}
                </span>
                <span>First seen: {formatRelativeTime(finding.first_detected_at)}</span>
                <Badge variant="outline" className="text-xs capitalize">{finding.confidence}</Badge>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </div>
          </CardContent>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t px-4 py-3 space-y-3 bg-muted/10">
            {finding.code_snippet && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Vulnerable Code</p>
                <pre className="text-xs bg-muted rounded-md p-3 overflow-x-auto font-mono">
                  <code>{finding.code_snippet}</code>
                </pre>
              </div>
            )}
            {finding.fix_suggestion && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Suggested Fix</p>
                <pre className="text-xs bg-emerald-50 dark:bg-emerald-950/20 rounded-md p-3 overflow-x-auto font-mono border border-emerald-200 dark:border-emerald-800">
                  <code>{finding.fix_suggestion}</code>
                </pre>
              </div>
            )}
            {finding.owasp_ids && finding.owasp_ids.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">OWASP:</span>
                {finding.owasp_ids.map((o) => (
                  <Badge key={o} variant="secondary" className="text-xs">{o}</Badge>
                ))}
              </div>
            )}
            {finding.metadata && (finding.metadata as Record<string, unknown>).references && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">References:</span>
                {((finding.metadata as Record<string, unknown>).references as string[]).slice(0, 3).map((ref) => (
                  <a
                    key={ref}
                    href={ref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-500 hover:underline flex items-center gap-0.5"
                  >
                    {new URL(ref).hostname}<ExternalLink className="h-3 w-3" />
                  </a>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2 pt-1">
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => onDismiss(finding.id)}
              >
                <EyeOff className="h-3 w-3 mr-1" />Dismiss
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => onFalsePositive(finding.id)}
              >
                <XCircle className="h-3 w-3 mr-1" />False Positive
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-xs text-orange-600"
                onClick={() => onIgnoreRule(finding.rule_id, finding.repository_id)}
              >
                <Ban className="h-3 w-3 mr-1" />Ignore Rule
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

function TopRulesTable({ summary }: { summary: SastSummary | undefined }) {
  if (!summary || Object.keys(summary.by_rule).length === 0) return null;
  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium">Top Rules</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 px-4 pb-3">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rule</TableHead>
              <TableHead className="text-right">Count</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(summary.by_rule).map(([rule, count]) => (
              <TableRow key={rule}>
                <TableCell className="font-mono text-xs">{rule}</TableCell>
                <TableCell className="text-right">{count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function TopFilesTable({ summary }: { summary: SastSummary | undefined }) {
  if (!summary || Object.keys(summary.by_file).length === 0) return null;
  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium">Most Affected Files</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 px-4 pb-3">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead className="text-right">Findings</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(summary.by_file).map(([file, count]) => (
              <TableRow key={file}>
                <TableCell className="font-mono text-xs truncate max-w-md">{file}</TableCell>
                <TableCell className="text-right">{count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function ScanHistory({ projectId }: { projectId: string }) {
  const { data: runs } = useProjectSastRuns(projectId);
  const [expanded, setExpanded] = useState(false);

  if (!runs || runs.length === 0) return null;

  const visible = expanded ? runs : runs.slice(0, 5);

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Scan History</CardTitle>
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
              run.status === "running" ? "text-amber-500" :
              "text-slate-400";
            const StatusIcon =
              run.status === "completed" ? CheckCircle2 :
              run.status === "failed" ? AlertTriangle :
              run.status === "running" ? Loader2 :
              Info;
            return (
              <div key={run.id} className="flex items-center gap-3 text-sm py-1">
                <StatusIcon className={`h-3.5 w-3.5 ${statusColor} ${run.status === "running" ? "animate-spin" : ""}`} />
                <span className="text-muted-foreground">{formatRelativeTime(run.created_at)}</span>
                <span className="text-muted-foreground">&middot;</span>
                <span>{run.findings_count} findings</span>
                {run.tool && <Badge variant="outline" className="text-xs">{run.tool}</Badge>}
                {run.commit_sha && (
                  <span className="font-mono text-xs text-muted-foreground">{run.commit_sha.slice(0, 7)}</span>
                )}
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
              started_at: r.created_at,
              findings_count: r.findings_count,
              status: r.status,
            }))}
          />
        )}
      </CardContent>
    </Card>
  );
}

export default function SecurityPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const qc = useQueryClient();
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [scanningRepoId, setScanningRepoId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [repos, setRepos] = useState<Repository[]>([]);

  useEffect(() => {
    api.listRepos(projectId).then(setRepos).catch(() => {});
  }, [projectId]);

  const filters = {
    ...(severityFilter && { severity: severityFilter }),
    ...(statusFilter ? { status: statusFilter } : {}),
  };

  const { data: summary, isLoading: summaryLoading } = useProjectSastSummary(projectId);
  const { data: findings, isLoading: findingsLoading } = useProjectSastFindings(projectId, filters);
  const { data: runs, refetch: refetchRuns } = useProjectSastRuns(projectId);

  const lastRun = runs?.[0];
  const isRunning = lastRun?.status === "running" || lastRun?.status === "queued";

  useEffect(() => {
    if (isRunning && lastRun && !activeRunId) {
      setActiveRunId(lastRun.id);
      setScanningRepoId(lastRun.repository_id);
    }
  }, [isRunning, lastRun, activeRunId]);

  const handleScanRepo = useCallback(async (repoId: string) => {
    if (scanningRepoId) return;
    try {
      setScanningRepoId(repoId);
      const run = await api.triggerSastScan(repoId);
      setActiveRunId(run.id);
    } catch {
      setScanningRepoId(null);
    }
  }, [scanningRepoId]);

  const handleDismiss = useCallback(async (findingId: string) => {
    const finding = findings?.find((f) => f.id === findingId);
    if (!finding) return;
    await api.dismissSastFinding(finding.repository_id, findingId);
    qc.invalidateQueries({ queryKey: queryKeys.sast.findings(projectId, "project") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.summary(projectId, "project") });
  }, [findings, projectId, qc]);

  const handleFalsePositive = useCallback(async (findingId: string) => {
    const finding = findings?.find((f) => f.id === findingId);
    if (!finding) return;
    await api.markSastFalsePositive(finding.repository_id, findingId);
    qc.invalidateQueries({ queryKey: queryKeys.sast.findings(projectId, "project") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.summary(projectId, "project") });
  }, [findings, projectId, qc]);

  const logUrl = activeRunId && scanningRepoId
    ? `${api.getApiBase()}/repositories/${scanningRepoId}/sast/runs/${activeRunId}/logs`
    : null;

  const handleIgnoreRule = useCallback(async (ruleId: string, repoId: string) => {
    try {
      await api.addRepoIgnoredRule(repoId, { rule_id: ruleId, reason: "Ignored from Security page" });
      qc.invalidateQueries({ queryKey: queryKeys.sast.findings(projectId, "project") });
      qc.invalidateQueries({ queryKey: queryKeys.sast.summary(projectId, "project") });
    } catch { /* ignore conflict */ }
  }, [projectId, qc]);

  const handleLogsDone = useCallback(() => {
    setActiveRunId(null);
    setScanningRepoId(null);
    refetchRuns();
    qc.invalidateQueries({ queryKey: queryKeys.sast.findings(projectId, "project") });
    qc.invalidateQueries({ queryKey: queryKeys.sast.summary(projectId, "project") });
  }, [projectId, qc, refetchRuns]);

  return (
    <div className="space-y-6">
      <SecurityScoreBanner
        summary={summary}
        isLoading={summaryLoading}
        lastRun={lastRun}
        repos={repos}
        onScanRepo={handleScanRepo}
        scanningRepoId={scanningRepoId}
        projectId={projectId}
      />

      {logUrl && scanningRepoId && (
        <SyncLogViewer logUrl={logUrl} compact title="SAST Scan Logs" onDone={handleLogsDone} />
      )}

      <SeveritySummaryCards summary={summary} isLoading={summaryLoading} />

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
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
        <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
          {STATUSES.map((s) => (
            <button
              key={s.value}
              onClick={() => setStatusFilter(s.value)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                statusFilter === s.value
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
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="border-l-4 border-l-muted">
              <CardContent className="flex items-start gap-3 py-3 px-4">
                <Skeleton className="h-7 w-7 rounded-md mt-0.5" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : findings && findings.length > 0 ? (
        <div className="space-y-2">
          {findings.map((f) => (
            <SastFindingRow
              key={f.id}
              finding={f}
              onDismiss={handleDismiss}
              onFalsePositive={handleFalsePositive}
              onIgnoreRule={handleIgnoreRule}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <ShieldCheck className="h-10 w-10 mb-2 text-emerald-500" />
            <p className="font-medium">No security findings</p>
            <p className="text-sm mt-1">
              {runs?.length
                ? "All clear! No open vulnerabilities detected."
                : "Run a SAST scan to check your repositories for security vulnerabilities."}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Breakdowns */}
      <div className="grid gap-4 md:grid-cols-2">
        <TopRulesTable summary={summary} />
        <TopFilesTable summary={summary} />
      </div>

      <ScanHistory projectId={projectId} />
    </div>
  );
}
