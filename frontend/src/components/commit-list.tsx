"use client";

import { GitCommitHorizontal, ChevronLeft, ChevronRight, GitMerge, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { CommitItem } from "@/lib/types";

interface CommitListProps {
  commits: CommitItem[];
  total: number;
  page: number;
  perPage: number;
  loading?: boolean;
  onPageChange: (page: number) => void;
  showRepo?: boolean;
}

export function CommitList({ commits, total, page, perPage, loading, onPageChange, showRepo = false }: CommitListProps) {
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-base">Commits ({total})</CardTitle>
        {totalPages > 1 && (
          <div className="flex items-center gap-2 text-sm">
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-muted-foreground">{page} / {totalPages}</span>
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="px-6 py-8 text-center text-muted-foreground animate-pulse">Loading commits...</div>
        ) : commits.length === 0 ? (
          <div className="px-6 py-8 text-center text-muted-foreground">No commits found</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">SHA</TableHead>
                <TableHead>Message</TableHead>
                {showRepo && <TableHead>Repository</TableHead>}
                <TableHead>Author</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">+/-</TableHead>
                <TableHead>Branches</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commits.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-xs">
                    <span className="flex items-center gap-1.5">
                      {c.is_merge ? (
                        <GitMerge className="h-3.5 w-3.5 text-violet-500 shrink-0" />
                      ) : (
                        <GitCommitHorizontal className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      )}
                      {c.commit_url ? (
                        <a
                          href={c.commit_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                        >
                          {c.sha.slice(0, 7)}
                          <ExternalLink className="h-2.5 w-2.5 opacity-50" />
                        </a>
                      ) : (
                        c.sha.slice(0, 7)
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-sm">{c.message?.split("\n")[0] || "-"}</TableCell>
                  {showRepo && <TableCell className="text-sm text-muted-foreground">{c.repository_name || "-"}</TableCell>}
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">{c.contributor_name || "-"}</TableCell>
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {new Date(c.authored_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right text-xs whitespace-nowrap">
                    <span className="text-emerald-500">+{c.lines_added}</span>
                    {" / "}
                    <span className="text-red-500">-{c.lines_deleted}</span>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {c.branches.slice(0, 3).map((b) => (
                        <Badge key={b} variant="secondary" className="text-[10px] px-1.5 py-0">{b}</Badge>
                      ))}
                      {c.branches.length > 3 && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">+{c.branches.length - 3}</Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
