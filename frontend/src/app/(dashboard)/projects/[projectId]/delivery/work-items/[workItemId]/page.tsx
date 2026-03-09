"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useWorkItemDetail } from "@/hooks/use-delivery";
import { useCustomFields } from "@/hooks/use-custom-fields";

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
  const { data: item, isLoading } = useWorkItemDetail(projectId, workItemId);
  const { data: customFieldConfigs = [] } = useCustomFields(projectId);

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
      .replace(/<\/font>/gi, "");
  }, [item?.description]);

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
      <Button variant="ghost" size="sm" asChild>
        <Link href={`/projects/${projectId}/delivery`}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Project
        </Link>
      </Button>

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
        <h1 className="text-2xl font-bold tracking-tight">{item.title}</h1>
      </div>

      {/* Description */}
      {cleanDescription && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-foreground prose-a:text-primary prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:text-sm prose-code:before:content-none prose-code:after:content-none prose-img:rounded-md"
              dangerouslySetInnerHTML={{ __html: cleanDescription }}
            />
          </CardContent>
        </Card>
      )}

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
