"use client";

import { use, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft, ChevronRight, ExternalLink, Bot, Info, Copy, Check, Plus, Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { StatCard } from "@/components/stat-card";
import { FilterBarSkeleton, StatRowSkeleton, TableSkeleton } from "@/components/page-skeleton";
import { Input } from "@/components/ui/input";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useProject } from "@/hooks/use-projects";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";
import { CodeSubTabs } from "@/components/code-sub-tabs";
import type { CodeReviewRunItem, PRListItem } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "completed", label: "Completed" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "failed", label: "Failed" },
];

const VERDICT_OPTIONS = [
  { value: "all", label: "All Verdicts" },
  { value: "approve", label: "Approve" },
  { value: "request_changes", label: "Request Changes" },
  { value: "comment", label: "Comment" },
];

const TRIGGER_OPTIONS = [
  { value: "all", label: "All Triggers" },
  { value: "webhook", label: "Webhook" },
  { value: "manual", label: "Manual" },
  { value: "scheduled", label: "Scheduled" },
];

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

function triggerLabel(t: string) {
  switch (t) {
    case "webhook": return "Webhook";
    case "manual": return "Manual";
    case "scheduled": return "Scheduled";
    default: return t;
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

function relativeTime(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="absolute top-2 right-2 p-1 rounded hover:bg-muted-foreground/10 text-muted-foreground"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function NewReviewDialog({
  projectId,
  repositories,
  onQueued,
}: {
  projectId: string;
  repositories: { id: string; name: string }[];
  onQueued: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [repoId, setRepoId] = useState(repositories.length === 1 ? repositories[0].id : "");
  const [search, setSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [selectedPr, setSelectedPr] = useState<PRListItem | null>(null);

  const { data: prResponse } = useQuery({
    queryKey: queryKeys.pullRequests.list(projectId, {
      repository_id: repoId || undefined,
      state: "open",
      search: search || undefined,
      page_size: 20,
    }),
    queryFn: () =>
      api.listPullRequests(projectId, {
        repository_id: repoId || undefined,
        state: "open",
        search: search || undefined,
        page_size: 20,
      }),
    enabled: open && !!projectId,
  });

  const prs = prResponse?.items ?? [];

  const handleSubmit = useCallback(async () => {
    if (!selectedPr) return;
    setSubmitting(true);
    try {
      await api.triggerCodeReview(projectId, selectedPr.repository_id, selectedPr.platform_pr_id);
      setOpen(false);
      setSelectedPr(null);
      setSearch("");
      onQueued();
    } catch (e) {
      console.error("Failed to trigger code review", e);
    } finally {
      setSubmitting(false);
    }
  }, [projectId, selectedPr, onQueued]);

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setSelectedPr(null); setSearch(""); } }}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <Plus className="h-3.5 w-3.5" /> New Review
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Request AI Code Review</DialogTitle>
          <DialogDescription>
            Select an open pull request to run the AI code reviewer on.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 pt-2">
          {repositories.length > 1 && (
            <Select value={repoId} onValueChange={(v) => { setRepoId(v); setSelectedPr(null); }}>
              <SelectTrigger>
                <SelectValue placeholder="Filter by repository…" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Repositories</SelectItem>
                {repositories.map((r) => (
                  <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search PRs by title or number…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setSelectedPr(null); }}
              className="pl-9"
            />
          </div>

          <div className="border rounded-md max-h-64 overflow-y-auto">
            {prs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">
                No open pull requests found.
              </p>
            ) : (
              prs.map((pr) => (
                <button
                  key={pr.id}
                  type="button"
                  onClick={() => setSelectedPr(pr)}
                  className={cn(
                    "w-full text-left px-3 py-2.5 text-sm border-b last:border-b-0 transition-colors",
                    selectedPr?.id === pr.id
                      ? "bg-primary/10 text-foreground"
                      : "hover:bg-muted/50",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">
                      <span className="text-muted-foreground mr-1">#{pr.platform_pr_id}</span>
                      {pr.title || "(untitled)"}
                    </span>
                    {selectedPr?.id === pr.id && (
                      <Check className="h-4 w-4 shrink-0 text-primary" />
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {pr.repository_name}
                    {pr.author_name && <> · {pr.author_name}</>}
                    {" · "}
                    <span className="text-emerald-600">+{pr.lines_added}</span>
                    {" / "}
                    <span className="text-red-600">-{pr.lines_deleted}</span>
                  </div>
                </button>
              ))
            )}
          </div>

          <Button
            className="w-full gap-1.5"
            disabled={!selectedPr || submitting}
            onClick={handleSubmit}
          >
            <Bot className={cn("h-4 w-4", submitting && "animate-pulse")} />
            {submitting ? "Queuing Review…" : "Request Review"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SetupGuideDialog() {
  const githubAction = `# .github/workflows/contributr-review.yml
name: Contributr Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: your-org/contributr/.github/actions/contributr-review@main
        with:
          contributr_url: \${{ secrets.CONTRIBUTR_URL }}
          webhook_secret: \${{ secrets.CONTRIBUTR_WEBHOOK_SECRET }}`;

  const curlExample = `curl -X POST \\
  https://contributr.example.com/api/webhooks/projects/<project-id>/code-reviews \\
  -H "Content-Type: application/json" \\
  -d '{"repository_id": "<repo-uuid>", "pr_number": 123}'`;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Info className="h-3.5 w-3.5" /> Setup Guide
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Automated Code Review Setup</DialogTitle>
          <DialogDescription>
            Configure webhooks so Contributr automatically reviews pull requests when they are opened or updated.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 pt-2 text-sm">
          {/* GitHub */}
          <section>
            <h3 className="font-semibold text-base mb-2">GitHub</h3>
            <div className="space-y-3">
              <div>
                <h4 className="font-medium mb-1">Option A: GitHub Action (recommended)</h4>
                <p className="text-muted-foreground mb-2">
                  Add this workflow to any repository tracked in Contributr:
                </p>
                <div className="relative">
                  <pre className="bg-muted rounded-md p-3 text-xs whitespace-pre-wrap break-all font-mono">{githubAction}</pre>
                  <CopyButton text={githubAction} />
                </div>
                <p className="text-muted-foreground mt-2 text-xs">
                  Set <code className="bg-muted px-1 rounded">CONTRIBUTR_URL</code> and{" "}
                  <code className="bg-muted px-1 rounded">CONTRIBUTR_WEBHOOK_SECRET</code> as repository secrets.
                </p>
              </div>
              <div>
                <h4 className="font-medium mb-1">Option B: GitHub Webhook (org-wide)</h4>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                  <li>Go to <strong className="text-foreground">Settings &rarr; Webhooks &rarr; Add webhook</strong></li>
                  <li>Payload URL: <code className="bg-muted px-1 rounded text-xs break-all">/api/webhooks/github</code></li>
                  <li>Content type: <code className="bg-muted px-1 rounded text-xs">application/json</code></li>
                  <li>Secret: your Contributr <code className="bg-muted px-1 rounded text-xs">SECRET_KEY</code></li>
                  <li>Events: select &quot;Pull requests&quot;</li>
                </ol>
              </div>
            </div>
          </section>

          <hr className="border-border" />

          {/* Azure DevOps */}
          <section>
            <h3 className="font-semibold text-base mb-2">Azure DevOps</h3>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li>Go to <strong className="text-foreground">Project Settings &rarr; Service hooks &rarr; Create subscription</strong></li>
              <li>Select <strong className="text-foreground">Web Hooks</strong> as the service</li>
              <li>Event: &quot;Pull request created&quot; and/or &quot;Pull request updated&quot;</li>
              <li>URL: <code className="bg-muted px-1 rounded text-xs">/api/webhooks/azure-devops</code></li>
              <li>HTTP header: <code className="bg-muted px-1 rounded text-xs">X-Azure-Token: &lt;SECRET_KEY&gt;</code></li>
            </ol>
          </section>

          <hr className="border-border" />

          {/* GitLab */}
          <section>
            <h3 className="font-semibold text-base mb-2">GitLab</h3>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li>Go to <strong className="text-foreground">Settings &rarr; Webhooks</strong></li>
              <li>URL: <code className="bg-muted px-1 rounded text-xs">/api/webhooks/gitlab</code></li>
              <li>Secret token: your Contributr <code className="bg-muted px-1 rounded text-xs">SECRET_KEY</code></li>
              <li>Trigger: check &quot;Merge request events&quot;</li>
            </ol>
          </section>

          <hr className="border-border" />

          {/* Manual */}
          <section>
            <h3 className="font-semibold text-base mb-2">Manual / API Trigger</h3>
            <p className="text-muted-foreground mb-2">
              Trigger a review for any tracked PR without webhooks:
            </p>
            <div className="relative">
              <pre className="bg-muted rounded-md p-3 text-xs whitespace-pre-wrap break-all font-mono">{curlExample}</pre>
              <CopyButton text={curlExample} />
            </div>
          </section>

          <hr className="border-border" />

          {/* Prerequisites */}
          <section>
            <h3 className="font-semibold text-base mb-2">Prerequisites</h3>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>A chat LLM provider configured for the <strong className="text-foreground">code-reviewer</strong> agent</li>
              <li>Platform credentials with write access in <strong className="text-foreground">Settings &rarr; Platform Credentials</strong></li>
              <li>The <code className="bg-muted px-1 rounded text-xs">SECRET_KEY</code> env var matching your webhook config</li>
            </ul>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function CodeReviewsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const { data: project } = useProject(projectId);
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("all");
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [triggerFilter, setTriggerFilter] = useState("all");
  const [repoFilter, setRepoFilter] = useState("__all__");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const filters = useMemo(() => ({
    status: statusFilter !== "all" ? statusFilter : undefined,
    verdict: verdictFilter !== "all" ? verdictFilter : undefined,
    trigger: triggerFilter !== "all" ? triggerFilter : undefined,
    repository_id: repoFilter !== "__all__" ? repoFilter : undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  }), [statusFilter, verdictFilter, triggerFilter, repoFilter, page]);

  const { data: reviews, isLoading: listLoading } = useQuery({
    queryKey: queryKeys.codeReviews.list(projectId, filters),
    queryFn: () => api.listCodeReviews(projectId, filters),
    enabled: !!projectId,
  });

  const { data: summary } = useQuery({
    queryKey: queryKeys.codeReviews.summary(projectId),
    queryFn: () => api.getCodeReviewSummary(projectId),
    enabled: !!projectId,
  });

  useRegisterUIContext("codeReviews", {
    reviews,
    summary,
    filters,
  });

  const handleReviewQueued = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.codeReviews.list(projectId, filters) });
    queryClient.invalidateQueries({ queryKey: queryKeys.codeReviews.summary(projectId) });
  }, [queryClient, projectId, filters]);

  if (!project) {
    return (
      <div className="space-y-6">
        <FilterBarSkeleton />
        <StatRowSkeleton />
        <TableSkeleton rows={8} cols={7} />
      </div>
    );
  }

  const approvalRate = summary && summary.completed > 0
    ? Math.round(((summary.by_verdict?.approve ?? 0) / summary.completed) * 100)
    : null;
  const failureRate = summary
    ? summary.total_runs > 0 ? Math.round((summary.failed / summary.total_runs) * 100) : 0
    : null;

  return (
    <div className="space-y-6">
      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-1 rounded-md border border-border bg-background p-0.5">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { setStatusFilter(opt.value); setPage(1); }}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-sm transition-colors",
                statusFilter === opt.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <Select value={verdictFilter} onValueChange={(v) => { setVerdictFilter(v); setPage(1); }}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="All Verdicts" />
          </SelectTrigger>
          <SelectContent>
            {VERDICT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={triggerFilter} onValueChange={(v) => { setTriggerFilter(v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All Triggers" />
          </SelectTrigger>
          <SelectContent>
            {TRIGGER_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {project.repositories.length > 1 && (
          <Select value={repoFilter} onValueChange={(v) => { setRepoFilter(v); setPage(1); }}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All Repos" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Repositories</SelectItem>
              {project.repositories.map((r) => (
                <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <div className="ml-auto flex items-center gap-2">
          <SetupGuideDialog />
          <NewReviewDialog
            projectId={projectId}
            repositories={project.repositories}
            onQueued={handleReviewQueued}
          />
        </div>
      </div>

      <CodeSubTabs projectId={projectId} />

      {/* Stat Cards */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard className={ANIM_CARD} style={stagger(0)} title="Total Reviews" value={summary.total_runs} />
          <StatCard
            className={ANIM_CARD}
            style={stagger(1)}
            title="Avg Findings"
            value={summary.avg_findings !== null ? summary.avg_findings : "—"}
          />
          <StatCard
            className={ANIM_CARD}
            style={stagger(2)}
            title="Approval Rate"
            value={approvalRate !== null ? `${approvalRate}%` : "—"}
          />
          <StatCard
            className={ANIM_CARD}
            style={stagger(3)}
            title="Failure Rate"
            value={failureRate !== null ? `${failureRate}%` : "—"}
          />
        </div>
      )}

      {/* Table */}
      {listLoading ? (
        <TableSkeleton rows={8} cols={8} />
      ) : reviews && reviews.length > 0 ? (
        <>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[30%]">Pull Request</TableHead>
                  <TableHead>Repository</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Verdict</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.map((run: CodeReviewRunItem) => (
                  <TableRow
                    key={run.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => {
                      window.location.href = `/projects/${projectId}/code/reviews/${run.id}`;
                    }}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          <span className="text-muted-foreground mr-1">#{run.platform_pr_number}</span>
                          {run.pr_title || "(untitled)"}
                        </span>
                        {run.review_url && (
                          <a
                            href={run.review_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{run.repository_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">
                        {triggerLabel(run.trigger)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={cn("text-[10px]", statusColor(run.status))}>
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {run.verdict ? (
                        <Badge variant="secondary" className={cn("text-[10px]", verdictColor(run.verdict))}>
                          {verdictLabel(run.verdict)}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm tabular-nums">
                      {run.findings_count !== null ? (
                        <span className={run.findings_count === 0 ? "text-muted-foreground" : ""}>
                          {run.findings_count}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm tabular-nums">
                      {formatDuration(run.started_at, run.completed_at)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {relativeTime(run.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {reviews.length >= pageSize && (
            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">Page {page}</span>
              <Button variant="outline" size="sm" disabled={reviews.length < pageSize} onClick={() => setPage(page + 1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Bot className="h-12 w-12 text-muted-foreground/40 mb-3" />
          <h3 className="text-lg font-medium">No code reviews found</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Configure webhooks or trigger a code review on any open PR to get started.
          </p>
        </div>
      )}
    </div>
  );
}
