"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, Users, GitCommitHorizontal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { FileTreeNode } from "@/lib/types";

interface FileTreeProps {
  nodes: FileTreeNode[];
  onSelectFile: (path: string) => void;
  selectedPath?: string;
}

function TreeNode({ node, depth, onSelectFile, selectedPath }: { node: FileTreeNode; depth: number; onSelectFile: (p: string) => void; selectedPath?: string }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const isDir = node.type === "directory";
  const isSelected = node.path === selectedPath;

  return (
    <div>
      <button
        className={`flex w-full items-center gap-1.5 py-1 px-2 text-sm rounded transition-colors hover:bg-muted/60 ${isSelected ? "bg-primary/10 text-primary" : ""}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => {
          if (isDir) setExpanded(!expanded);
          else onSelectFile(node.path);
        }}
      >
        {isDir ? (
          <>
            {expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
            {expanded ? <FolderOpen className="h-3.5 w-3.5 text-amber-500 shrink-0" /> : <Folder className="h-3.5 w-3.5 text-amber-500 shrink-0" />}
          </>
        ) : (
          <>
            <span className="w-3.5" />
            <File className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          </>
        )}
        <span className="truncate font-mono text-xs">{node.name}</span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
            <GitCommitHorizontal className="h-3 w-3" />{node.commits}
          </span>
          {node.contributors === 1 ? (
            <Badge variant="outline" className="text-[9px] px-1 py-0 text-amber-600 border-amber-300">1 owner</Badge>
          ) : (
            <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
              <Users className="h-3 w-3" />{node.contributors}
            </span>
          )}
        </span>
      </button>
      {isDir && expanded && node.children?.map((child) => (
        <TreeNode key={child.path} node={child} depth={depth + 1} onSelectFile={onSelectFile} selectedPath={selectedPath} />
      ))}
    </div>
  );
}

export function FileTree({ nodes, onSelectFile, selectedPath }: FileTreeProps) {
  if (nodes.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No file data available. Sync the repository to populate file-level data.</p>;
  }
  return (
    <div className="rounded-lg border bg-background p-2 max-h-[600px] overflow-y-auto">
      {nodes.map((n) => (
        <TreeNode key={n.path} node={n} depth={0} onSelectFile={onSelectFile} selectedPath={selectedPath} />
      ))}
    </div>
  );
}
