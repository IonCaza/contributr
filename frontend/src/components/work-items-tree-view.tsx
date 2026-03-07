"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ChevronRight, ChevronDown, ExternalLink } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { WorkItemTreeNode } from "@/lib/types";

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
  else if (lower.includes("resolved") || lower.includes("done") || lower.includes("completed"))
    cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed"))
    cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new"))
    cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return <Badge variant="secondary" className={`text-[10px] ${cls}`}>{state}</Badge>;
}

function collectVisibleRows(
  roots: WorkItemTreeNode[],
  expandedIds: Set<string>,
  defaultExpandDepth: number,
): { node: WorkItemTreeNode; depth: number }[] {
  const out: { node: WorkItemTreeNode; depth: number }[] = [];
  function walk(nodes: WorkItemTreeNode[], depth: number) {
    for (const node of nodes) {
      out.push({ node, depth });
      const isExpanded = depth < defaultExpandDepth || expandedIds.has(node.id);
      if (node.children.length > 0 && isExpanded) {
        walk(node.children, depth + 1);
      }
    }
  }
  walk(roots, 0);
  return out;
}

export interface WorkItemsTreeViewProps {
  projectId: string;
  roots: WorkItemTreeNode[];
  totalCount: number;
  isLoading?: boolean;
}

export function WorkItemsTreeView({
  projectId,
  roots,
  totalCount,
  isLoading,
}: WorkItemsTreeViewProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());
  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const visibleRows = useMemo(
    () => collectVisibleRows(roots, expandedIds, 1),
    [roots, expandedIds],
  );

  if (isLoading) {
    return (
      <Card>
        <div className="py-8 text-center text-sm text-muted-foreground animate-pulse">
          Loading tree...
        </div>
      </Card>
    );
  }

  if (roots.length === 0) {
    return (
      <Card>
        <div className="py-8 text-center text-sm text-muted-foreground">
          No work items found. Sync from Azure DevOps or adjust filters.
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">ID</TableHead>
            <TableHead className="w-24">Type</TableHead>
            <TableHead>Title</TableHead>
            <TableHead className="w-24">State</TableHead>
            <TableHead className="w-32">Assigned To</TableHead>
            <TableHead className="w-20 text-right">Points</TableHead>
            <TableHead className="w-24">Priority</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleRows.map(({ node: wi, depth }) => {
            const hasChildren = wi.children.length > 0;
            const isExpanded = depth < 1 || expandedIds.has(wi.id);
            return (
              <TableRow key={wi.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell
                  className="text-xs text-muted-foreground align-middle"
                  style={{ paddingLeft: `${12 + depth * 20}px` }}
                >
                  <span className="inline-flex items-center gap-0.5">
                    {hasChildren ? (
                      <button
                        type="button"
                        className="p-0.5 -m-0.5 rounded hover:bg-muted"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          toggleExpanded(wi.id);
                        }}
                        aria-label={isExpanded ? "Collapse" : "Expand"}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                        )}
                      </button>
                    ) : (
                      <span className="w-4 inline-block" />
                    )}
                    #{wi.platform_work_item_id}
                  </span>
                </TableCell>
                <TableCell>
                  <Badge
                    variant="secondary"
                    className={`text-[10px] ${TYPE_COLORS[wi.work_item_type] || ""}`}
                  >
                    {TYPE_LABELS[wi.work_item_type] || wi.work_item_type}
                  </Badge>
                </TableCell>
                <TableCell className="font-medium max-w-md truncate" title={wi.title}>
                  <Link
                    href={`/projects/${projectId}/delivery/work-items/${wi.id}`}
                    className="hover:underline"
                  >
                    {wi.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <StateTag state={wi.state} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground truncate max-w-[8rem]" title={wi.assigned_to?.name ?? "Unassigned"}>
                  {wi.assigned_to?.name ?? <span className="italic">Unassigned</span>}
                </TableCell>
                <TableCell className="text-right">{wi.story_points ?? "—"}</TableCell>
                <TableCell className="text-xs">{wi.priority ? `P${wi.priority}` : "—"}</TableCell>
                <TableCell>
                  {wi.platform_url && (
                    <a
                      href={wi.platform_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {totalCount > 0 && (
        <div className="px-4 py-2 border-t text-sm text-muted-foreground">
          Showing {visibleRows.length} of {totalCount} items in tree
        </div>
      )}
    </Card>
  );
}
