"use client";

import { useEffect, useState } from "react";
import { Flame, AlertTriangle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api-client";
import type { HotspotFile } from "@/lib/types";

interface HotspotTableProps {
  repoId: string;
  branch?: string;
  onSelectFile?: (path: string) => void;
}

export function HotspotTable({ repoId, branch, onSelectFile }: HotspotTableProps) {
  const [hotspots, setHotspots] = useState<HotspotFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getHotspots(repoId, 50, branch).then(setHotspots).finally(() => setLoading(false));
  }, [repoId, branch]);

  if (loading) return <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading hotspots...</div>;
  if (hotspots.length === 0) return <p className="py-8 text-center text-sm text-muted-foreground">No file data available. Sync the repository to populate.</p>;

  const maxCommits = Math.max(...hotspots.map((h) => h.commit_count));

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>File</TableHead>
            <TableHead className="text-right">Commits</TableHead>
            <TableHead className="text-right">Contributors</TableHead>
            <TableHead className="text-right">+/-</TableHead>
            <TableHead>Risk</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {hotspots.map((h) => {
            const heatPct = h.commit_count / maxCommits;
            const isSingleOwner = h.contributor_count === 1;
            const isHot = heatPct > 0.5;
            return (
              <TableRow
                key={h.file_path}
                className={onSelectFile ? "cursor-pointer hover:bg-muted/50" : ""}
                onClick={() => onSelectFile?.(h.file_path)}
              >
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    {isHot && <Flame className="h-3.5 w-3.5 text-orange-500 shrink-0" />}
                    <span className="font-mono text-xs truncate max-w-sm">{h.file_path}</span>
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">{h.commit_count}</TableCell>
                <TableCell className="text-right tabular-nums">{h.contributor_count}</TableCell>
                <TableCell className="text-right text-xs whitespace-nowrap">
                  <span className="text-emerald-500">+{h.total_lines_added.toLocaleString()}</span>
                  {" / "}
                  <span className="text-red-500">-{h.total_lines_deleted.toLocaleString()}</span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    {isSingleOwner && (
                      <Badge variant="outline" className="text-[9px] px-1 py-0 text-amber-600 border-amber-300">
                        <AlertTriangle className="h-2.5 w-2.5 mr-0.5" />single owner
                      </Badge>
                    )}
                    {isHot && (
                      <Badge variant="outline" className="text-[9px] px-1 py-0 text-orange-600 border-orange-300">
                        hotspot
                      </Badge>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
