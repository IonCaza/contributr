"use client";

import { use, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  ArrowLeft, Save, GitBranch, GitPullRequest, GitMerge,
  Trash2, FileText, Loader2, ExternalLink,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import type { Adr } from "@/lib/types";

function statusColor(s: string) {
  switch (s) {
    case "proposed": return "bg-blue-500/15 text-blue-700 dark:text-blue-400";
    case "accepted": return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "deprecated": return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
    case "superseded": return "bg-purple-500/15 text-purple-700 dark:text-purple-400";
    case "rejected": return "bg-red-500/15 text-red-700 dark:text-red-400";
    default: return "bg-muted text-muted-foreground";
  }
}

function extractTitle(md: string): string {
  const match = md.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : "";
}

function allowedStatuses(current: string, location: string): string[] {
  const wasInMain = location === "in_repo" || location === "removed_from_repo";
  switch (current) {
    case "proposed":
      return wasInMain ? ["proposed", "accepted"] : ["proposed", "rejected"];
    case "accepted":
      return ["accepted", "deprecated", "superseded"];
    case "deprecated":
    case "superseded":
    case "rejected":
      return [current];
    default:
      return [current];
  }
}

export default function AdrEditorPage({ params }: { params: Promise<{ projectId: string; adrId: string }> }) {
  const { projectId, adrId } = use(params);
  const qc = useQueryClient();
  const router = useRouter();
  const [content, setContent] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [supersedeOpen, setSupersedeOpen] = useState(false);
  const [supersedeSearch, setSupersedeSearch] = useState("");

  const { data: adr, isLoading } = useQuery({
    queryKey: queryKeys.adrs.detail(projectId, adrId),
    queryFn: () => api.getAdr(projectId, adrId),
    enabled: !!projectId && !!adrId,
  });

  const { data: allAdrs = [] } = useQuery({
    queryKey: queryKeys.adrs.list(projectId, { _supersede: true }),
    queryFn: () => api.listAdrs(projectId),
    enabled: !!projectId && supersedeOpen,
  });

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["adrs", projectId] });
  }, [qc, projectId]);

  const activeContent = content ?? adr?.content ?? "";
  const activeTitle = useMemo(() => extractTitle(activeContent), [activeContent]);
  const activeStatus = status ?? adr?.status ?? "proposed";

  const hasChanges = (content !== null && content !== adr?.content)
    || (status !== null && status !== adr?.status);

  function setTitleInContent(newTitle: string) {
    const c = content ?? adr?.content ?? "";
    const headingRe = /^#\s+.+$/m;
    if (headingRe.test(c)) {
      setContent(c.replace(headingRe, `# ${newTitle}`));
    } else {
      setContent(`# ${newTitle}\n\n${c}`);
    }
  }

  const saveAdr = useMutation({
    mutationFn: () => api.updateAdr(projectId, adrId, {
      content: content ?? undefined,
      status: status ?? undefined,
    }),
    onSuccess: () => {
      setContent(null);
      setStatus(null);
      invalidate();
    },
  });

  const onActionError = (err: Error) => setActionError(err.message || "An error occurred");

  const commitAdr = useMutation({
    mutationFn: () => api.commitAdr(projectId, adrId),
    onSuccess: () => { setActionError(null); invalidate(); },
    onError: onActionError,
  });

  const createPr = useMutation({
    mutationFn: () => api.createAdrPr(projectId, adrId),
    onSuccess: () => { setActionError(null); invalidate(); },
    onError: onActionError,
  });

  const mergePr = useMutation({
    mutationFn: () => api.mergeAdrPr(projectId, adrId),
    onSuccess: () => { setActionError(null); invalidate(); },
    onError: onActionError,
  });

  const deleteAdr = useMutation({
    mutationFn: () => api.deleteAdr(projectId, adrId),
    onSuccess: () => router.push(`/projects/${projectId}/adrs`),
    onError: onActionError,
  });

  const supersedeAdr = useMutation({
    mutationFn: (newAdrId: string) => api.supersedeAdr(projectId, adrId, newAdrId),
    onSuccess: () => {
      setActionError(null);
      setSupersedeOpen(false);
      setStatus(null);
      invalidate();
    },
    onError: onActionError,
  });

  function handleStatusChange(newStatus: string) {
    if (newStatus === "superseded") {
      setSupersedeOpen(true);
      return;
    }
    setStatus(newStatus);
  }

  if (isLoading || !adr) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  const statusOptions = allowedStatuses(adr.status, adr.location);
  const isArchivePending = (adr.status === "deprecated" || adr.status === "superseded")
    && adr.file_path && !adr.file_path.includes("/archive/");

  return (
    <div className="space-y-4">
      {/* Back + header */}
      <Link
        href={`/projects/${projectId}/adrs`}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to ADRs
      </Link>

      {/* Removed-from-repo banner */}
      {adr.location === "removed_from_repo" && (
        <Card className="border-orange-500/30 bg-orange-500/5 p-3 flex items-center justify-between">
          <p className="text-sm text-orange-700 dark:text-orange-400">
            This ADR was removed from the repository{adr.removed_from_repo_at ? ` on ${new Date(adr.removed_from_repo_at).toLocaleDateString()}` : ""}. Click <strong>Commit</strong> to restore it.
          </p>
        </Card>
      )}

      {/* Deprecated / superseded archive banner */}
      {adr.status === "deprecated" && isArchivePending && (
        <Card className="border-amber-500/30 bg-amber-500/5 p-3">
          <p className="text-sm text-amber-700 dark:text-amber-400">
            This ADR is deprecated. Click <strong>Commit</strong> to archive it in the repository.
          </p>
        </Card>
      )}
      {adr.status === "superseded" && isArchivePending && (
        <Card className="border-purple-500/30 bg-purple-500/5 p-3">
          <p className="text-sm text-purple-700 dark:text-purple-400">
            This ADR is superseded{adr.superseded_by_id && <> by <Link href={`/projects/${projectId}/adrs/${adr.superseded_by_id}`} className="underline font-medium">another ADR</Link></>}. Click <strong>Commit</strong> to archive it in the repository.
          </p>
        </Card>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 mr-auto min-w-0 flex-1">
          <span className="text-muted-foreground font-mono text-sm shrink-0">ADR-{adr.adr_number}</span>
          <Badge variant="secondary" className={cn("text-[10px] shrink-0",
            adr.location === "in_repo" ? "bg-green-500/15 text-green-700 dark:text-green-400" :
            adr.location === "removed_from_repo" ? "bg-orange-500/15 text-orange-700 dark:text-orange-400" :
            "bg-muted text-muted-foreground"
          )}>
            {adr.location === "in_repo" ? "In Repo" : adr.location === "removed_from_repo" ? "Removed" : "Draft"}
          </Badge>
          <Input
            value={activeTitle}
            onChange={(e) => setTitleInContent(e.target.value)}
            className="text-lg font-bold flex-1 min-w-0 border-none shadow-none p-0 h-auto focus-visible:ring-0"
          />
        </div>

        <Select value={activeStatus} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((s) => (
              <SelectItem key={s} value={s}>
                <span className="capitalize">{s}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button size="sm" onClick={() => saveAdr.mutate()} disabled={!hasChanges || saveAdr.isPending}>
          {saveAdr.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save
        </Button>

        <Button variant="outline" size="sm" onClick={() => commitAdr.mutate()} disabled={commitAdr.isPending}>
          {commitAdr.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitBranch className="mr-2 h-4 w-4" />}
          Commit
        </Button>

        <Button variant="outline" size="sm" onClick={() => createPr.mutate()} disabled={!adr.last_committed_sha || createPr.isPending}>
          {createPr.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitPullRequest className="mr-2 h-4 w-4" />}
          Create PR
        </Button>

        {adr.pr_url && (
          <Button variant="outline" size="sm" onClick={() => mergePr.mutate()} disabled={mergePr.isPending}>
            {mergePr.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitMerge className="mr-2 h-4 w-4" />}
            Merge PR
          </Button>
        )}

        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleteOpen(true)}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {actionError && (
        <Card className="border-destructive/30 bg-destructive/5 p-3 flex items-center justify-between">
          <p className="text-sm text-destructive">{actionError}</p>
          <button onClick={() => setActionError(null)} className="text-xs text-destructive/70 hover:text-destructive">Dismiss</button>
        </Card>
      )}

      {/* Editor + Preview + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
        {/* Editor area */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => setShowPreview(false)}
              className={cn("text-sm px-2 py-1 rounded", !showPreview ? "bg-muted font-medium" : "text-muted-foreground")}
            >
              Edit
            </button>
            <button
              onClick={() => setShowPreview(true)}
              className={cn("text-sm px-2 py-1 rounded", showPreview ? "bg-muted font-medium" : "text-muted-foreground")}
            >
              Preview
            </button>
          </div>

          {showPreview ? (
            <Card className="p-6 min-h-[500px]">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {activeContent || "*No content yet*"}
                </ReactMarkdown>
              </div>
            </Card>
          ) : (
            <Textarea
              value={activeContent}
              onChange={(e) => setContent(e.target.value)}
              rows={25}
              className="font-mono text-sm min-h-[500px]"
              placeholder="Write your ADR in Markdown..."
            />
          )}
        </div>

        {/* Metadata sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <span className="text-muted-foreground">Status:</span>{" "}
                <Badge variant="secondary" className={cn("text-[10px] capitalize", statusColor(activeStatus))}>
                  {activeStatus}
                </Badge>
              </div>
              <div>
                <span className="text-muted-foreground">Number:</span>{" "}
                <span className="font-mono">{adr.adr_number}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Created:</span>{" "}
                {new Date(adr.created_at).toLocaleDateString()}
              </div>
              {adr.updated_at && (
                <div>
                  <span className="text-muted-foreground">Modified:</span>{" "}
                  {new Date(adr.updated_at).toLocaleDateString()}
                </div>
              )}
              {adr.committed_to_repo_at && (
                <div>
                  <span className="text-muted-foreground">Committed to repo:</span>{" "}
                  {new Date(adr.committed_to_repo_at).toLocaleDateString()}
                </div>
              )}
              {adr.removed_from_repo_at && (
                <div>
                  <span className="text-muted-foreground">Removed from repo:</span>{" "}
                  {new Date(adr.removed_from_repo_at).toLocaleDateString()}
                </div>
              )}
              {adr.file_path && (
                <div>
                  <span className="text-muted-foreground">File:</span>{" "}
                  <span className="font-mono text-xs">{adr.file_path}</span>
                </div>
              )}
              {adr.last_committed_sha && (
                <div>
                  <span className="text-muted-foreground">SHA:</span>{" "}
                  <span className="font-mono text-xs">{adr.last_committed_sha.slice(0, 10)}</span>
                </div>
              )}
              {adr.pr_url && (
                <div>
                  <a href={adr.pr_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-blue-500 hover:underline">
                    <ExternalLink className="h-3 w-3" /> View PR
                  </a>
                </div>
              )}
              {adr.superseded_by_id && (
                <div>
                  <span className="text-muted-foreground">Superseded by:</span>{" "}
                    <Link href={`/projects/${projectId}/adrs/${adr.superseded_by_id}`} className="text-blue-500 hover:underline text-xs">
                    View
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>

          {hasChanges && (
            <Card className="border-amber-500/30 bg-amber-500/5 p-3">
              <p className="text-xs text-amber-700 dark:text-amber-400">You have unsaved changes.</p>
            </Card>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete ADR"
        description={<>This will permanently delete <span className="font-semibold">ADR-{adr.adr_number}: {adr.title}</span>. This action cannot be undone.</>}
        confirmLabel="Delete"
        onConfirm={() => deleteAdr.mutate()}
      />

      {/* Supersede dialog */}
      <Dialog open={supersedeOpen} onOpenChange={(open) => { if (!open) setSupersedeOpen(false); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Supersede ADR-{adr.adr_number}</DialogTitle>
            <DialogDescription>Select the ADR that replaces this one.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              placeholder="Search ADRs..."
              value={supersedeSearch}
              onChange={(e) => setSupersedeSearch(e.target.value)}
            />
            <div className="max-h-64 overflow-y-auto space-y-1">
              {allAdrs
                .filter((a: Adr) => a.id !== adrId)
                .filter((a: Adr) =>
                  !supersedeSearch || a.title.toLowerCase().includes(supersedeSearch.toLowerCase())
                  || `ADR-${a.adr_number}`.toLowerCase().includes(supersedeSearch.toLowerCase())
                )
                .map((a: Adr) => (
                  <button
                    key={a.id}
                    onClick={() => supersedeAdr.mutate(a.id)}
                    disabled={supersedeAdr.isPending}
                    className="w-full text-left px-3 py-2 rounded-md hover:bg-muted transition-colors text-sm"
                  >
                    <span className="font-mono text-muted-foreground mr-2">ADR-{a.adr_number}</span>
                    {a.title}
                  </button>
                ))
              }
              {allAdrs.filter((a: Adr) => a.id !== adrId).length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">No other ADRs in this project.</p>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
