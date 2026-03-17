"use client";

import { use, useMemo, useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Pencil, X, Save, Loader2, ChevronLeft, ChevronRight, Clock, User2, ArrowRightLeft, FileEdit, RefreshCw, AlertTriangle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useWorkItemDetail, useUpdateWorkItem, usePullWorkItem, useAcceptDraft, useDiscardDraft, useWorkItemActivities } from "@/hooks/use-delivery";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useCustomFields } from "@/hooks/use-custom-fields";
import { RichTextEditor } from "@/components/rich-text-editor";
import { DescriptionDiffEditor } from "@/components/description-diff-editor";
import { useChatTrigger } from "@/hooks/use-chat-trigger";
import type { WorkItemActivityEntry } from "@/lib/types";

const TYPE_COLORS: Record<string, string> = {
  epic: "bg-purple-500/10 text-purple-700 dark:text-purple-400",
  feature: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
  user_story: "bg-green-500/10 text-green-700 dark:text-green-400",
  task: "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
  bug: "bg-red-500/10 text-red-700 dark:text-red-400",
};

const TYPE_LABELS: Record<string, string> = {
  epic: "Epic",
  feature: "Feature",
  user_story: "User Story",
  task: "Task",
  bug: "Bug",
};

function StateTag({ state }: { state: string }) {
  const lower = state.toLowerCase();
  let cls = "bg-muted text-muted-foreground";
  if (lower.includes("active") || lower.includes("progress"))
    cls = "bg-blue-500/10 text-blue-700 dark:text-blue-400";
  else if (
    lower.includes("resolved") ||
    lower.includes("done") ||
    lower.includes("completed")
  )
    cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed"))
    cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new"))
    cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return (
    <Badge variant="secondary" className={`text-[10px] ${cls}`}>
      {state}
    </Badge>
  );
}

function fmt(date: string | null | undefined) {
  if (!date) return "—";
  return new Date(date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function WorkItemDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; workItemId: string }>;
}) {
  const { projectId, workItemId } = use(params);

  const [editing, setEditing] = useState(false);
  const [aiEditing, setAiEditing] = useState(false);

  const { data: item, isLoading } = useWorkItemDetail(projectId, workItemId, {
    refetchInterval: aiEditing ? 3000 : false,
  });
  const { data: customFieldConfigs = [] } = useCustomFields(projectId);
  const updateMutation = useUpdateWorkItem(projectId, workItemId);
  const pullMutation = usePullWorkItem(projectId, workItemId);
  const acceptDraftMutation = useAcceptDraft(projectId, workItemId);
  const discardDraftMutation = useDiscardDraft(projectId, workItemId);
  const { openChat } = useChatTrigger();
  const [proposedHtml, setProposedHtml] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  const baselineRef = useRef<{ title: string; description: string; updated_at: string } | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);
  const pendingPayloadRef = useRef<{ title?: string; description?: string } | null>(null);

  const fieldDisplayNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const cfg of customFieldConfigs) {
      map[cfg.field_reference_name] = cfg.display_name;
    }
    return map;
  }, [customFieldConfigs]);

  const cleanDescription = useMemo(() => {
    if (!item?.description) return "";
    return item.description
      .replace(/\s*style="[^"]*"/gi, "")
      .replace(/<font[^>]*>/gi, "")
      .replace(/<\/font>/gi, "")
      .replace(/<span[^>]*>\s*<\/span>/gi, "")
      .replace(/(<div><br\s*\/?><\/div>\s*){2,}/gi, "<div><br/></div>");
  }, [item?.description]);

  const handleEdit = useCallback(() => {
    if (!item) return;
    setEditTitle(item.title);
    setEditDescription(item.description || "");
    setSaveError(null);
    baselineRef.current = {
      title: item.title,
      description: item.description || "",
      updated_at: item.updated_at || "",
    };
    setEditing(true);
  }, [item]);

  const handleCancel = useCallback(() => {
    setEditing(false);
    setSaveError(null);
    baselineRef.current = null;
    pendingPayloadRef.current = null;
  }, []);

  const doSave = useCallback((payload: { title?: string; description?: string }) => {
    updateMutation.mutate(payload, {
      onSuccess: () => {
        setEditing(false);
        baselineRef.current = null;
        pendingPayloadRef.current = null;
      },
      onError: (err) => setSaveError(err instanceof Error ? err.message : "Save failed"),
    });
  }, [updateMutation]);

  const handleSave = useCallback(() => {
    if (!item) return;
    setSaveError(null);
    const payload: { title?: string; description?: string } = {};
    if (editTitle !== (baselineRef.current?.title ?? item.title)) payload.title = editTitle;
    if (editDescription !== (baselineRef.current?.description ?? item.description ?? "")) payload.description = editDescription;
    if (Object.keys(payload).length === 0) {
      setEditing(false);
      return;
    }

    pendingPayloadRef.current = payload;

    pullMutation.mutate(undefined, {
      onSuccess: (fresh) => {
        const baseline = baselineRef.current;
        const remoteChanged =
          baseline &&
          (fresh.title !== baseline.title ||
            (fresh.description ?? "") !== baseline.description ||
            (fresh.updated_at ?? "") !== baseline.updated_at);

        if (remoteChanged) {
          setConflictOpen(true);
        } else {
          doSave(payload);
        }
      },
      onError: () => {
        doSave(payload);
      },
    });
  }, [item, editTitle, editDescription, pullMutation, doSave]);

  const handleForceOverwrite = useCallback(() => {
    setConflictOpen(false);
    if (pendingPayloadRef.current) {
      doSave(pendingPayloadRef.current);
    }
  }, [doSave]);

  const handleConflictCancel = useCallback(() => {
    setConflictOpen(false);
    pendingPayloadRef.current = null;
  }, []);

  const handlePull = useCallback(() => {
    pullMutation.mutate(undefined, {
      onSuccess: (fresh) => {
        if (editing) {
          setEditTitle(fresh.title);
          setEditDescription(fresh.description || "");
          baselineRef.current = {
            title: fresh.title,
            description: fresh.description || "",
            updated_at: fresh.updated_at || "",
          };
        }
      },
    });
  }, [pullMutation, editing]);

  // Sync draft_description from server into local state while AI editing
  useEffect(() => {
    if (aiEditing && item?.draft_description && item.draft_description !== proposedHtml) {
      setProposedHtml(item.draft_description);
    }
  }, [aiEditing, item?.draft_description]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAiEdit = useCallback(() => {
    if (!item) return;
    setAiEditing(true);
    setProposedHtml(item.draft_description || "");
    openChat(
      "delivery-analyst",
      `I'm looking at work item #${item.platform_work_item_id}: "${item.title}". Help me improve its description. Use read_work_item_description to see the current content, then propose an improved version.`,
    );
  }, [item, openChat]);

  const handleAcceptDraft = useCallback(
    (html: string) => {
      if (!item) return;
      acceptDraftMutation.mutate(undefined, {
        onSuccess: () => setAiEditing(false),
      });
    },
    [item, acceptDraftMutation],
  );

  const handleKeepOriginal = useCallback(() => {
    discardDraftMutation.mutate(undefined, {
      onSuccess: () => {
        setAiEditing(false);
        setProposedHtml("");
      },
    });
  }, [discardDraftMutation]);

  const handleDiscardAi = useCallback(() => {
    discardDraftMutation.mutate(undefined, {
      onSuccess: () => {
        setAiEditing(false);
        setProposedHtml("");
      },
    });
  }, [discardDraftMutation]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        Loading work item...
      </div>
    );
  }

  if (!item) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/projects/${projectId}/delivery`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Link>
        </Button>
        <p className="text-muted-foreground">Work item not found.</p>
      </div>
    );
  }

  const priorityLabel = item.priority != null ? `P${item.priority}` : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/projects/${projectId}/delivery`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handlePull}
            disabled={pullMutation.isPending}
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${pullMutation.isPending ? "animate-spin" : ""}`} />
            {pullMutation.isPending ? "Pulling..." : "Pull Latest"}
          </Button>
          {!editing && !aiEditing && (
            <>
              <Button variant="outline" size="sm" onClick={handleAiEdit}>
                <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                Edit with AI
              </Button>
              <Button variant="outline" size="sm" onClick={handleEdit}>
                <Pencil className="mr-1.5 h-3.5 w-3.5" />
                Edit
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Header */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="secondary"
            className={TYPE_COLORS[item.work_item_type] || ""}
          >
            {TYPE_LABELS[item.work_item_type] || item.work_item_type}
          </Badge>
          <span className="text-muted-foreground text-sm">
            #{item.platform_work_item_id}
          </span>
          <StateTag state={item.state} />
          {priorityLabel && (
            <Badge variant="outline" className="text-[10px]">
              {priorityLabel}
            </Badge>
          )}
          {item.platform_url && (
            <Button variant="ghost" size="sm" className="h-7 px-2" asChild>
              <a
                href={item.platform_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Button>
          )}
        </div>
        {editing ? (
          <Input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            className="text-2xl font-bold tracking-tight h-auto py-1"
          />
        ) : (
          <h1 className="text-2xl font-bold tracking-tight">{item.title}</h1>
        )}
      </div>

      {/* Description */}
      {aiEditing ? (
        <DescriptionDiffEditor
          originalHtml={item.description || ""}
          proposedHtml={proposedHtml}
          onProposedChange={setProposedHtml}
          onAccept={handleAcceptDraft}
          onKeepOriginal={handleKeepOriginal}
          onDiscard={handleDiscardAi}
          isLoading={acceptDraftMutation.isPending || discardDraftMutation.isPending}
        />
      ) : editing ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-base">Description</CardTitle>
            <div className="flex items-center gap-2">
              {saveError && (
                <span className="text-xs text-destructive">{saveError}</span>
              )}
              <Button variant="ghost" size="sm" onClick={handleCancel} disabled={updateMutation.isPending}>
                <X className="mr-1 h-3.5 w-3.5" />
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} disabled={updateMutation.isPending || pullMutation.isPending}>
                {updateMutation.isPending || pullMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-3.5 w-3.5" />
                )}
                {pullMutation.isPending ? "Checking..." : updateMutation.isPending ? "Saving..." : "Save to DevOps"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <RichTextEditor content={editDescription} onChange={setEditDescription} />
          </CardContent>
        </Card>
      ) : cleanDescription ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="prose prose-sm dark:prose-invert max-w-none ado-description prose-headings:text-foreground prose-a:text-primary prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:text-sm prose-code:before:content-none prose-code:after:content-none prose-img:rounded-md"
              dangerouslySetInnerHTML={{ __html: cleanDescription }}
            />
          </CardContent>
        </Card>
      ) : !editing ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground italic">No description.</p>
          </CardContent>
        </Card>
      ) : null}

      {/* Attributes grid */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">People & Location</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <PersonRow
              label="Assignee"
              person={item.assigned_to}
              fallback="Unassigned"
            />
            <PersonRow
              label="Created by"
              person={item.created_by}
              fallback="—"
            />
            <Row label="Iteration" value={item.iteration?.name ?? "—"} />
            <Row label="Area Path" value={item.area_path ?? "—"} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Effort</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row
              label="Story Points"
              value={item.story_points != null ? String(item.story_points) : "—"}
            />
            <Row
              label="Original Estimate"
              value={item.original_estimate != null ? `${item.original_estimate}h` : "—"}
            />
            <Row
              label="Remaining Work"
              value={item.remaining_work != null ? `${item.remaining_work}h` : "—"}
            />
            <Row
              label="Completed Work"
              value={item.completed_work != null ? `${item.completed_work}h` : "—"}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Timeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Created" value={fmt(item.created_at)} />
            <Row label="Activated" value={fmt(item.activated_at)} />
            <Row label="Resolved" value={fmt(item.resolved_at)} />
            <Row label="Closed" value={fmt(item.closed_at)} />
            <Row label="Last Updated" value={fmt(item.updated_at)} />
          </CardContent>
        </Card>
      </div>

      {/* Tags */}
      {item.tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">Tags:</span>
          {item.tags.map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>
      )}

      {/* Custom Fields */}
      {item.custom_fields &&
        Object.keys(item.custom_fields).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Custom Fields</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2 text-sm">
                {Object.entries(item.custom_fields).map(([key, val]) => {
                  const label = fieldDisplayNames[key] || key.replace(/^Custom\./, "").replace(/([A-Z])/g, " $1").trim();
                  return <Row key={key} label={label} value={String(val ?? "—")} />;
                })}
              </div>
            </CardContent>
          </Card>
        )}

      {/* Parent */}
      {item.parent && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Parent</CardTitle>
          </CardHeader>
          <CardContent>
            <Link
              href={`/projects/${projectId}/delivery/work-items/${item.parent.id}`}
              className="flex items-center gap-2 hover:underline"
            >
              <Badge
                variant="secondary"
                className={`text-[10px] ${TYPE_COLORS[item.parent.work_item_type] || ""}`}
              >
                {TYPE_LABELS[item.parent.work_item_type] ||
                  item.parent.work_item_type}
              </Badge>
              <span className="font-medium">{item.parent.title}</span>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Children */}
      {item.children.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Children ({item.children.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">Points</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {item.children.map((child) => (
                  <TableRow key={child.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={`text-[10px] ${TYPE_COLORS[child.work_item_type] || ""}`}
                      >
                        {TYPE_LABELS[child.work_item_type] ||
                          child.work_item_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${child.id}`}
                        className="font-medium hover:underline"
                      >
                        {child.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StateTag state={child.state} />
                    </TableCell>
                    <TableCell className="text-right">
                      {child.story_points ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Linked Commits */}
      {item.linked_commits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Linked Commits ({item.linked_commits.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SHA</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>Author</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Link Type</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {item.linked_commits.map((commit) => (
                  <TableRow key={commit.id}>
                    <TableCell className="font-mono text-xs">
                      {commit.sha.slice(0, 8)}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm">
                      {commit.message ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {commit.contributor?.name ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                      {new Date(commit.authored_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">
                        {commit.link_type}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Activity Log */}
      <ActivityLog projectId={projectId} workItemId={workItemId} />

      <AlertDialog open={conflictOpen} onOpenChange={setConflictOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Work Item Changed in DevOps
            </AlertDialogTitle>
            <AlertDialogDescription>
              This work item has been modified in Azure DevOps since you started editing.
              You can overwrite the remote version with your changes or cancel to review the latest version first.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleConflictCancel}>
              Cancel &amp; Review
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleForceOverwrite} className="bg-amber-600 hover:bg-amber-700">
              Overwrite Anyway
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

function PersonRow({
  label,
  person,
  fallback,
}: {
  label: string;
  person: { id: string; name: string | null } | null;
  fallback: string;
}) {
  const name = person?.name;
  const isKnown = name && name !== "unknown";
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground shrink-0">{label}</span>
      {isKnown ? (
        <Link
          href={`/contributors/${person.id}`}
          className="text-right font-medium text-primary hover:underline"
        >
          {name}
        </Link>
      ) : (
        <span className="text-right font-medium">{name ?? fallback}</span>
      )}
    </div>
  );
}

const ACTION_LABELS: Record<string, string> = {
  created: "Created",
  state_changed: "State changed",
  assigned: "Reassigned",
  field_changed: "Field updated",
  commented: "Commented",
};

function ActionIcon({ action }: { action: string }) {
  switch (action) {
    case "created": return <Clock className="h-3.5 w-3.5 text-green-500" />;
    case "state_changed": return <ArrowRightLeft className="h-3.5 w-3.5 text-blue-500" />;
    case "assigned": return <User2 className="h-3.5 w-3.5 text-amber-500" />;
    default: return <FileEdit className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

function friendlyFieldName(field: string | null): string {
  if (!field) return "";
  return field
    .replace(/^System\./, "")
    .replace(/^Microsoft\.VSTS\.\w+\./, "")
    .replace(/([A-Z])/g, " $1")
    .trim();
}

function ActivityLog({ projectId, workItemId }: { projectId: string; workItemId: string }) {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const { data, isLoading } = useWorkItemActivities(projectId, workItemId, { page, page_size: pageSize });
  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Activity Log {data ? `(${data.total})` : ""}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground animate-pulse">Loading activity...</p>}
        {data && data.items.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No activity recorded yet. Run a delivery sync to import activity history.</p>
        )}
        {data && data.items.length > 0 && (
          <div className="space-y-4">
            <div className="relative border-l-2 border-muted pl-6 space-y-4">
              {data.items.map((a: WorkItemActivityEntry) => (
                <div key={a.id} className="relative">
                  <div className="absolute -left-[31px] top-1 rounded-full bg-background border-2 border-muted p-1">
                    <ActionIcon action={a.action} />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium">
                        {a.contributor ? (
                          <Link href={`/contributors/${a.contributor.id}`} className="text-primary hover:underline">
                            {a.contributor.name ?? "Unknown"}
                          </Link>
                        ) : (
                          "System"
                        )}
                      </span>
                      <span className="text-muted-foreground">
                        {ACTION_LABELS[a.action] || a.action}
                        {a.field_name ? `: ${friendlyFieldName(a.field_name)}` : ""}
                      </span>
                    </div>
                    {(a.old_value || a.new_value) && a.action !== "created" && (
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        {a.old_value && (
                          <span className="line-through truncate max-w-[200px]" title={a.old_value}>
                            {a.old_value}
                          </span>
                        )}
                        {a.old_value && a.new_value && <span>&rarr;</span>}
                        {a.new_value && (
                          <span className="font-medium text-foreground truncate max-w-[200px]" title={a.new_value}>
                            {a.new_value}
                          </span>
                        )}
                      </div>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {fmt(a.activity_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-2">
                <p className="text-xs text-muted-foreground">
                  Page {page} of {totalPages}
                </p>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
