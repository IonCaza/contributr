"use client";

import { useState } from "react";
import { GitCommitHorizontal, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, GitMerge, ExternalLink, FileCode2, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { CommitItem, CommitDetail } from "@/lib/types";
import { api } from "@/lib/api-client";

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
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CommitDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function toggleExpand(commitId: string) {
    if (expandedId === commitId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(commitId);
    setDetailLoading(true);
    try {
      const d = await api.getCommitDetail(commitId);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  const colCount = showRepo ? 8 : 7;

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
                <TableHead className="w-8"></TableHead>
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
                <>
                  <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50" onClick={() => toggleExpand(c.id)}>
                    <TableCell className="w-8 px-2">
                      {expandedId === c.id ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                    </TableCell>
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
                            onClick={(e) => e.stopPropagation()}
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
                  {expandedId === c.id && (
                    <TableRow key={`${c.id}-detail`}>
                      <TableCell colSpan={colCount} className="bg-muted/30 p-4">
                        {detailLoading ? (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading details...</div>
                        ) : detail ? (
                          <div className="space-y-3">
                            {detail.message && detail.message.includes("\n") && (
                              <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-background rounded p-2 border">{detail.message}</pre>
                            )}
                            {detail.files.length > 0 ? (
                              <div>
                                <div className="text-xs font-semibold mb-1.5 flex items-center gap-1.5"><FileCode2 className="h-3.5 w-3.5" /> Files changed ({detail.files.length})</div>
                                <div className="space-y-0.5 max-h-64 overflow-y-auto">
                                  {detail.files.map((f) => (
                                    <div key={f.id} className="flex items-center justify-between text-xs font-mono py-0.5 px-2 rounded hover:bg-muted/50">
                                      <span className="truncate mr-4">{f.file_path}</span>
                                      <span className="shrink-0">
                                        <span className="text-emerald-500">+{f.lines_added}</span>
                                        {" "}
                                        <span className="text-red-500">-{f.lines_deleted}</span>
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">No file-level data available. Sync the repository to populate.</p>
                            )}
                          </div>
                        ) : (
                          <p className="text-xs text-muted-foreground">Could not load commit details.</p>
                        )}
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
