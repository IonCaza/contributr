"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft, ExternalLink, Bot, Clock, AlertTriangle,
  CheckCircle2, XCircle, MessageSquare, Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

function statusColor(s: string) {
  switch (s) {
    case "completed": return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "running": return "bg-blue-500/15 text-blue-700 dark:text-blue-400";
    case "queued": return "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400";
    case "failed": return "bg-red-500/15 text-red-700 dark:text-red-400";
    default: return "bg-muted text-muted-foreground";
  }
}

function verdictColor(v: string) {
  switch (v) {
    case "approve": return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "request_changes": return "bg-red-500/15 text-red-700 dark:text-red-400";
    case "comment": return "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400";
    default: return "bg-muted text-muted-foreground";
  }
}

function verdictLabel(v: string) {
  switch (v) {
    case "approve": return "Approved";
    case "request_changes": return "Changes Requested";
    case "comment": return "Commented";
    default: return v;
  }
}

function verdictIcon(v: string) {
  switch (v) {
    case "approve": return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case "request_changes": return <XCircle className="h-5 w-5 text-red-500" />;
    case "comment": return <MessageSquare className="h-5 w-5 text-yellow-500" />;
    default: return <Bot className="h-5 w-5 text-muted-foreground" />;
  }
}

function formatDuration(start: string | null, end: string | null) {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 0) return "—";
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

export default function ReviewDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; runId: string }>;
}) {
  const { projectId, runId } = use(params);

  const { data: run, isLoading } = useQuery({
    queryKey: queryKeys.codeReviews.detail(projectId, runId),
    queryFn: () => api.getCodeReview(projectId, runId),
    enabled: !!projectId && !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "queued" || status === "running") return 5000;
      return false;
    },
  });

  useRegisterUIContext("review-detail", run ? {
    run_id: runId,
    pr_number: run.platform_pr_number,
    pr_title: run.pr_title,
    repository: run.repository_name,
    status: run.status,
    verdict: run.verdict,
    findings_count: run.findings_count,
    trigger: run.trigger,
    created_at: run.created_at,
  } : null);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <AlertTriangle className="h-12 w-12 text-muted-foreground/40 mb-3" />
        <h3 className="text-lg font-medium">Review not found</h3>
        <Link href={`/projects/${projectId}/code/reviews`}>
          <Button variant="ghost" className="mt-4">
            <ArrowLeft className="h-4 w-4 mr-2" /> Back to reviews
          </Button>
        </Link>
      </div>
    );
  }

  const isActive = run.status === "queued" || run.status === "running";

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href={`/projects/${projectId}/code/reviews`}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" /> Back to reviews
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <Bot className="h-6 w-6 text-primary" />
            <span className="text-muted-foreground font-normal">#{run.platform_pr_number}</span>
            {run.pr_title || "Code Review"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {run.repository_name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isActive && (
            <div className="flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              {run.status === "queued" ? "Waiting..." : "Reviewing..."}
            </div>
          )}
          <Badge variant="secondary" className={cn("text-xs", statusColor(run.status))}>
            {run.status}
          </Badge>
          {run.verdict && (
            <Badge variant="secondary" className={cn("text-xs", verdictColor(run.verdict))}>
              {verdictLabel(run.verdict)}
            </Badge>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            {run.verdict ? verdictIcon(run.verdict) : <Bot className="h-5 w-5 text-muted-foreground" />}
            <div>
              <div className="text-xs text-muted-foreground">Verdict</div>
              <div className="text-sm font-semibold">{run.verdict ? verdictLabel(run.verdict) : "Pending"}</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-xs text-muted-foreground">Findings</div>
              <div className="text-sm font-semibold">
                {run.findings_count !== null ? run.findings_count : "—"}
              </div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-xs text-muted-foreground">Duration</div>
              <div className="text-sm font-semibold">
                {formatDuration(run.started_at, run.completed_at)}
              </div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <Bot className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-xs text-muted-foreground">Trigger</div>
              <div className="text-sm font-semibold capitalize">{run.trigger}</div>
            </div>
          </div>
        </Card>
      </div>

      {/* View on platform */}
      {run.review_url && (
        <a
          href={run.review_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button variant="outline" className="gap-2">
            <ExternalLink className="h-4 w-4" />
            View Review on Platform
          </Button>
        </a>
      )}

      {/* Error alert */}
      {run.status === "failed" && run.error_message && (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-red-700 dark:text-red-400 flex items-center gap-2">
              <XCircle className="h-4 w-4" />
              Review Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs text-red-600 dark:text-red-400 whitespace-pre-wrap font-mono">
              {run.error_message}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Timestamps */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd className="font-medium">{new Date(run.created_at).toLocaleString()}</dd>
            </div>
            {run.started_at && (
              <div>
                <dt className="text-muted-foreground">Started</dt>
                <dd className="font-medium">{new Date(run.started_at).toLocaleString()}</dd>
              </div>
            )}
            {run.completed_at && (
              <div>
                <dt className="text-muted-foreground">Completed</dt>
                <dd className="font-medium">{new Date(run.completed_at).toLocaleString()}</dd>
              </div>
            )}
            {run.pr_state && (
              <div>
                <dt className="text-muted-foreground">PR State</dt>
                <dd className="font-medium capitalize">{run.pr_state}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
