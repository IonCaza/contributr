"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Users, AlertTriangle, ChevronDown, ChevronRight, Merge, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useContributors, useDuplicateContributors, useMergeContributors } from "@/hooks/use-contributors";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";
import type { DuplicateGroup } from "@/lib/types";

export default function ContributorsPage() {
  const { data: contributors = [], isLoading } = useContributors();
  const { data: duplicates = [] } = useDuplicateContributors();
  const mergeMutation = useMergeContributors();
  const [search, setSearch] = useState("");
  const [dupExpanded, setDupExpanded] = useState(true);
  const [mergeGroup, setMergeGroup] = useState<DuplicateGroup | null>(null);
  const [mergeTarget, setMergeTarget] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const contribMap = new Map(contributors.map((c) => [c.id, c]));
  const dupContributorIds = new Set(duplicates.flatMap((g) => g.contributor_ids));

  useRegisterUIContext("contributors", {
    totalContributors: contributors.length,
    duplicateGroups: duplicates.length,
    contributors: contributors.slice(0, 50).map((c) => ({
      id: c.id,
      name: c.canonical_name,
      email: c.canonical_email,
      projectCount: c.projects.length,
    })),
  });

  const toggleSelect = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  function openManualMerge() {
    if (selected.size < 2) return;
    const ids = Array.from(selected);
    setMergeGroup({ group_key: "manual", reason: "Manual selection", contributor_ids: ids });
    setMergeTarget(ids[0]);
  }

  async function handleMerge() {
    if (!mergeGroup || !mergeTarget) return;
    const sources = mergeGroup.contributor_ids.filter((id) => id !== mergeTarget);
    for (const sourceId of sources) {
      await mergeMutation.mutateAsync({ sourceId, targetId: mergeTarget });
    }
    setMergeGroup(null);
    setMergeTarget(null);
    setSelected(new Set());
  }

  const filtered = contributors.filter(
    (c) =>
      c.canonical_name.toLowerCase().includes(search.toLowerCase()) ||
      c.canonical_email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Contributors</h1>
        <p className="text-muted-foreground">All contributors across all projects and repositories</p>
      </div>

      <div className="flex items-center gap-3">
        <Input placeholder="Search by name or email..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
        {selected.size >= 2 && (
          <Button size="sm" variant="outline" onClick={openManualMerge}>
            <Merge className="mr-1.5 h-3.5 w-3.5" />
            Merge {selected.size} selected
          </Button>
        )}
        {selected.size === 1 && (
          <span className="text-xs text-muted-foreground">Select at least 2 contributors to merge</span>
        )}
      </div>

      {duplicates.length > 0 && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <button
            onClick={() => setDupExpanded((v) => !v)}
            className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium hover:bg-amber-500/10 transition-colors"
          >
            {dupExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Possible Duplicates ({duplicates.length} group{duplicates.length !== 1 ? "s" : ""} found)
          </button>
          {dupExpanded && (
            <div className="space-y-3 px-4 pb-4">
              {duplicates.map((group) => (
                <div key={group.group_key} className="rounded-lg border border-border bg-background p-3 space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">{group.reason}</p>
                  <div className="space-y-1">
                    {group.contributor_ids.map((id) => {
                      const c = contribMap.get(id);
                      if (!c) return null;
                      return (
                        <div key={id} className="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm">
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                            {c.canonical_name.charAt(0).toUpperCase()}
                          </div>
                          <span className="font-medium min-w-0 truncate">{c.canonical_name}</span>
                          <span className="text-muted-foreground text-xs truncate">{c.canonical_email}</span>
                          {c.projects.length > 0 && (
                            <div className="flex gap-1 ml-auto shrink-0">
                              {c.projects.map((p) => (
                                <Badge key={p.id} variant="secondary" className="text-[10px] px-1.5 py-0">
                                  {p.name}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs"
                      onClick={() => {
                        setMergeGroup(group);
                        setMergeTarget(group.contributor_ids[0]);
                      }}
                    >
                      <Merge className="mr-1.5 h-3 w-3" />
                      Merge
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground"><div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />Loading...</div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <p className="text-lg font-medium">No contributors found</p>
            <p className="text-sm text-muted-foreground">Sync a repository to discover contributors</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Projects</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((c) => (
                <TableRow key={c.id} className={selected.has(c.id) ? "bg-primary/5" : undefined}>
                  <TableCell className="w-10 pr-0">
                    <Checkbox
                      checked={selected.has(c.id)}
                      onCheckedChange={() => toggleSelect(c.id)}
                      aria-label={`Select ${c.canonical_name}`}
                    />
                  </TableCell>
                  <TableCell>
                    <Link href={`/contributors/${c.id}`} className="flex items-center gap-2 font-medium hover:underline">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                        {c.canonical_name.charAt(0).toUpperCase()}
                      </div>
                      {c.canonical_name}
                      {dupContributorIds.has(c.id) && (
                        <span className="ml-1 inline-block h-2 w-2 rounded-full bg-amber-500" title="Possible duplicate" />
                      )}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{c.canonical_email}</TableCell>
                  <TableCell>
                    {c.projects.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {c.projects.map((p) => (
                          <Link key={p.id} href={`/projects/${p.id}/code`}>
                            <Badge variant="secondary" className="text-xs hover:bg-accent cursor-pointer">
                              {p.name}
                            </Badge>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">-</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <Dialog open={!!mergeGroup} onOpenChange={(v) => { if (!v) { setMergeGroup(null); setMergeTarget(null); } }}>
        <DialogContent className="max-w-xl sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Merge Contributors</DialogTitle>
            <DialogDescription>
              Select which identity to keep as the canonical record. All commits, stats, and aliases from the other identit{mergeGroup && mergeGroup.contributor_ids.length > 2 ? "ies" : "y"} will be merged into it.
            </DialogDescription>
          </DialogHeader>
          {mergeGroup && (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">{mergeGroup.reason}</p>
              <div className="space-y-1.5">
                {mergeGroup.contributor_ids.map((id) => {
                  const c = contribMap.get(id);
                  if (!c) return null;
                  const isTarget = mergeTarget === id;
                  return (
                    <button
                      key={id}
                      onClick={() => setMergeTarget(id)}
                      className={`flex w-full items-center gap-3 rounded-lg border p-3 text-left text-sm transition-colors ${
                        isTarget
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-accent"
                      }`}
                    >
                      <div className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                        isTarget ? "border-primary bg-primary text-primary-foreground" : "border-border"
                      }`}>
                        {isTarget && <Check className="h-3 w-3" />}
                      </div>
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                        {c.canonical_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium truncate">{c.canonical_name}</p>
                        <p className="text-xs text-muted-foreground break-all">{c.canonical_email}</p>
                      </div>
                      {isTarget && (
                        <Badge variant="default" className="shrink-0 text-[10px]">Keep</Badge>
                      )}
                    </button>
                  );
                })}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => { setMergeGroup(null); setMergeTarget(null); }}>
                  Cancel
                </Button>
                <Button onClick={handleMerge} disabled={!mergeTarget || mergeMutation.isPending}>
                  {mergeMutation.isPending ? "Merging..." : "Merge"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
