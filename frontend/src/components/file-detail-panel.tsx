"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { FileCode2, Users, GitCommitHorizontal, Crown, Loader2, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

interface FileDetailPanelProps {
  repoId: string;
  filePath: string;
  branch?: string;
}

export function FileDetailPanel({ repoId, filePath, branch }: FileDetailPanelProps) {
  const { data: detail, isLoading } = useQuery({
    queryKey: queryKeys.repos.fileDetail(repoId, filePath, branch),
    queryFn: () => api.getFileDetail(repoId, filePath, branch),
    enabled: !!repoId && !!filePath,
  });

  if (isLoading) return <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading file details...</div>;
  if (!detail) return <p className="py-8 text-center text-sm text-muted-foreground">Could not load file details.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileCode2 className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-mono text-sm font-semibold truncate">{detail.path}</h3>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xl font-bold">{detail.total_commits}</div>
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1"><GitCommitHorizontal className="h-3 w-3" /> Commits</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xl font-bold text-emerald-500">+{detail.total_lines_added.toLocaleString()}</div>
            <div className="text-xs text-muted-foreground">Added</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-xl font-bold text-red-500">-{detail.total_lines_deleted.toLocaleString()}</div>
            <div className="text-xs text-muted-foreground">Deleted</div>
          </CardContent>
        </Card>
      </div>

      {detail.primary_owner && (
        <div className="flex items-center gap-2 rounded-lg border p-3 bg-amber-500/5">
          <Crown className="h-4 w-4 text-amber-500" />
          <span className="text-sm font-medium">Primary owner:</span>
          <Link href={`/contributors/${detail.primary_owner.id}`} className="text-sm text-primary hover:underline">{detail.primary_owner.name}</Link>
          <Badge variant="secondary" className="text-[10px]">{detail.primary_owner.commits} commits</Badge>
        </div>
      )}

      <div>
        <h4 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><Users className="h-4 w-4" /> Contributors ({detail.contributors.length})</h4>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="text-right">Commits</TableHead>
                <TableHead className="text-right">+/-</TableHead>
                <TableHead>Last Touched</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.contributors.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>
                    <Link href={`/contributors/${c.id}`} className="text-sm font-medium hover:underline">{c.name}</Link>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{c.commits}</TableCell>
                  <TableCell className="text-right text-xs">
                    <span className="text-emerald-500">+{c.lines_added.toLocaleString()}</span>
                    {" / "}
                    <span className="text-red-500">-{c.lines_deleted.toLocaleString()}</span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{c.last_touched ? new Date(c.last_touched).toLocaleDateString() : "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>

      {detail.recent_commits.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><GitCommitHorizontal className="h-4 w-4" /> Recent Commits</h4>
          <Card>
            <div className="space-y-0 divide-y">
              {detail.recent_commits.map((c) => (
                <div key={c.id} className="flex items-center gap-3 px-4 py-2">
                  {c.commit_url ? (
                    <a href={c.commit_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline shrink-0">
                      {c.sha.slice(0, 7)}
                      <ExternalLink className="h-2.5 w-2.5 opacity-50" />
                    </a>
                  ) : (
                    <code className="text-xs text-primary shrink-0">{c.sha.slice(0, 7)}</code>
                  )}
                  <span className="text-sm truncate flex-1">{c.message?.split("\n")[0] || "-"}</span>
                  <span className="text-xs text-muted-foreground shrink-0 whitespace-nowrap">{c.contributor_name}</span>
                  <span className="text-xs text-muted-foreground shrink-0">{new Date(c.authored_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
