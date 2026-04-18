"use client";

import Link from "next/link";
import { Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useBacklogFeatureRollup } from "@/hooks/use-delivery";

export function FeatureRollupCard({
  projectId,
  teamId,
  title = "Feature backlog rollup",
  limit = 10,
}: {
  projectId: string;
  teamId?: string;
  title?: string;
  limit?: number;
}) {
  const { data, isLoading } = useBacklogFeatureRollup(projectId, {
    team_id: teamId,
    limit,
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
        {data?.tshirt_custom_field && (
          <p className="text-[11px] text-muted-foreground">
            T-shirt sizing via <code className="font-mono">{data.tshirt_custom_field}</code>
          </p>
        )}
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <p className="px-6 py-4 text-sm text-muted-foreground">Loading…</p>
        ) : !data || data.features.length === 0 ? (
          <p className="px-6 py-4 text-sm text-muted-foreground">No features with child items in this window.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Feature</TableHead>
                <TableHead className="text-right">Items</TableHead>
                <TableHead className="text-right">SP (done / total)</TableHead>
                <TableHead className="text-right">Done %</TableHead>
                <TableHead>T-shirt mix</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.features.map((f) => {
                const tshirtSized = f.tshirt_counts.filter((t) => t.count > 0).slice(0, 5);
                return (
                  <TableRow key={f.feature_id}>
                    <TableCell className="max-w-[260px]">
                      <Link
                        href={`/projects/${projectId}/delivery/work-items/${f.feature_id}`}
                        className="hover:underline"
                      >
                        <div className="font-medium truncate">{f.title ?? `#${f.platform_work_item_id}`}</div>
                        <div className="text-[11px] text-muted-foreground">#{f.platform_work_item_id} · {f.state}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <div>
                        {f.completed_items}
                        <span className="text-muted-foreground"> / {f.total_items}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {f.completed_points.toFixed(0)}<span className="text-muted-foreground"> / {f.total_points.toFixed(0)}</span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <Badge
                        variant={f.completion_pct >= 80 ? "secondary" : f.completion_pct >= 40 ? "outline" : "destructive"}
                        className="text-[10px]"
                      >
                        {Math.round(f.completion_pct)}%
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {tshirtSized.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {tshirtSized.map((t) => (
                            <Badge key={t.size} variant="outline" className="text-[10px]">
                              {t.size}: {t.count}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
