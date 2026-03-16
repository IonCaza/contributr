"use client";

import { use, useState, useCallback } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import type { Adr } from "@/lib/types";

const STATUS_OPTIONS = ["proposed", "accepted", "deprecated", "superseded", "rejected"];

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

export default function AdrEditorPage({ params }: { params: Promise<{ projectId: string; adrId: string }> }) {
  const { projectId, adrId } = use(params);
  const qc = useQueryClient();
  const router = useRouter();
  const [title, setTitle] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: adr, isLoading } = useQuery({
    queryKey: queryKeys.adrs.detail(projectId, adrId),
    queryFn: () => api.getAdr(projectId, adrId),
    enabled: !!projectId && !!adrId,
  });

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.adrs.detail(projectId, adrId) });
    qc.invalidateQueries({ queryKey: queryKeys.adrs.list(projectId) });
  }, [qc, projectId, adrId]);

  const activeTitle = title ?? adr?.title ?? "";
  const activeContent = content ?? adr?.content ?? "";
  const activeStatus = status ?? adr?.status ?? "proposed";

  const hasChanges = (title !== null && title !== adr?.title)
    || (content !== null && content !== adr?.content)
    || (status !== null && status !== adr?.status);

  const saveAdr = useMutation({
    mutationFn: () => api.updateAdr(projectId, adrId, {
      title: title ?? undefined,
      content: content ?? undefined,
      status: status ?? undefined,
    }),
    onSuccess: (data) => {
      setTitle(null);
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

  if (isLoading || !adr) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Back + header */}
      <Link
        href={`/projects/${projectId}/adrs`}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to ADRs
      </Link>

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 mr-auto">
          <span className="text-muted-foreground font-mono text-sm">ADR-{adr.adr_number}</span>
          <Input
            value={activeTitle}
            onChange={(e) => setTitle(e.target.value)}
            className="text-lg font-bold w-96 border-none shadow-none p-0 h-auto focus-visible:ring-0"
          />
        </div>

        <Select value={activeStatus} onValueChange={(v) => setStatus(v)}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((s) => (
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
    </div>
  );
}
