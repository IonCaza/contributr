"use client";

import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import type { DailyStat } from "@/lib/types";
import { useMemo } from "react";

interface StatDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  metric: string;
  daily: DailyStat[];
  contributorNames?: Record<string, string>;
  repoNames?: Record<string, string>;
}

function resolveName(id: string, map?: Record<string, string>): string {
  return map?.[id] || id.slice(0, 8);
}

export function StatDetailSheet({ open, onOpenChange, title, metric, daily, contributorNames, repoNames }: StatDetailSheetProps) {
  const totals = useMemo(() => {
    let commits = 0, lines_added = 0, lines_deleted = 0;
    for (const d of daily) { commits += d.commits; lines_added += d.lines_added; lines_deleted += d.lines_deleted; }
    return { commits, lines_added, lines_deleted };
  }, [daily]);

  const byContributor = useMemo(() => {
    const map = new Map<string, { id: string; name: string; commits: number; lines_added: number; lines_deleted: number; days: Set<string> }>();
    for (const d of daily) {
      const key = d.contributor_id;
      const ex = map.get(key) || { id: key, name: resolveName(key, contributorNames), commits: 0, lines_added: 0, lines_deleted: 0, days: new Set<string>() };
      ex.commits += d.commits;
      ex.lines_added += d.lines_added;
      ex.lines_deleted += d.lines_deleted;
      ex.days.add(d.date.slice(0, 10));
      map.set(key, ex);
    }
    return Array.from(map.values()).sort((a, b) => b.commits - a.commits).slice(0, 20);
  }, [daily, contributorNames]);

  const byRepo = useMemo(() => {
    const map = new Map<string, { id: string; name: string; commits: number; lines_added: number; lines_deleted: number }>();
    for (const d of daily) {
      const key = d.repository_id;
      const ex = map.get(key) || { id: key, name: resolveName(key, repoNames), commits: 0, lines_added: 0, lines_deleted: 0 };
      ex.commits += d.commits;
      ex.lines_added += d.lines_added;
      ex.lines_deleted += d.lines_deleted;
      map.set(key, ex);
    }
    return Array.from(map.values()).sort((a, b) => b.commits - a.commits);
  }, [daily, repoNames]);

  const chartData = useMemo(() => {
    const byDate = new Map<string, { commits: number; lines_added: number; lines_deleted: number; unique_contributors: Set<string> }>();
    for (const d of daily) {
      const key = d.date.slice(0, 10);
      const ex = byDate.get(key) || { commits: 0, lines_added: 0, lines_deleted: 0, unique_contributors: new Set<string>() };
      ex.commits += d.commits;
      ex.lines_added += d.lines_added;
      ex.lines_deleted += d.lines_deleted;
      ex.unique_contributors.add(d.contributor_id);
      byDate.set(key, ex);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({
        date: date.slice(5),
        commits: vals.commits,
        lines_added: vals.lines_added,
        lines_deleted: vals.lines_deleted,
        contributors: vals.unique_contributors.size,
      }));
  }, [daily]);

  const uniqueContributors = useMemo(() => new Set(daily.map((d) => d.contributor_id)).size, [daily]);

  const cumulativeContributorChart = useMemo(() => {
    const byDate = new Map<string, Set<string>>();
    for (const d of daily) {
      const key = d.date.slice(0, 10);
      if (!byDate.has(key)) byDate.set(key, new Set());
      byDate.get(key)!.add(d.contributor_id);
    }
    const sortedDates = Array.from(byDate.keys()).sort();
    const seenAll = new Set<string>();
    return sortedDates.map((date) => {
      for (const cid of byDate.get(date)!) seenAll.add(cid);
      return {
        date: date.slice(5),
        lines_added: seenAll.size,
        lines_deleted: 0,
        commits: byDate.get(date)!.size,
      };
    });
  }, [daily]);

  const activeDayCount = useMemo(() => new Set(daily.map((d) => d.date.slice(0, 10))).size, [daily]);
  const calendarDayCount = useMemo(() => {
    if (daily.length === 0) return 0;
    const dates = daily.map((d) => d.date.slice(0, 10)).sort();
    const first = new Date(dates[0]);
    const last = new Date(dates[dates.length - 1]);
    return Math.max(1, Math.round((last.getTime() - first.getTime()) / 86400000) + 1);
  }, [daily]);
  const avgCommitsPerDay = calendarDayCount > 0 ? Math.round((totals.commits / calendarDayCount) * 10) / 10 : 0;

  const commitsChartData = useMemo(() => {
    const byDate = new Map<string, number>();
    for (const d of daily) {
      const key = d.date.slice(0, 10);
      byDate.set(key, (byDate.get(key) || 0) + d.commits);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, commits]) => ({
        date: date.slice(5),
        lines_added: commits,
        lines_deleted: 0,
        commits,
      }));
  }, [daily]);

  const churnChartData = useMemo(() => {
    const byDate = new Map<string, { added: number; deleted: number }>();
    for (const d of daily) {
      const key = d.date.slice(0, 10);
      const ex = byDate.get(key) || { added: 0, deleted: 0 };
      ex.added += d.lines_added;
      ex.deleted += d.lines_deleted;
      byDate.set(key, ex);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({
        date: date.slice(5),
        lines_added: vals.added,
        lines_deleted: vals.deleted,
        commits: 0,
      }));
  }, [daily]);

  const churnRatio = totals.lines_added > 0 ? Math.round((totals.lines_deleted / totals.lines_added) * 100) / 100 : 0;

  const giniData = useMemo(() => {
    const sorted = [...byContributor].sort((a, b) => a.commits - b.commits);
    const total = sorted.reduce((s, c) => s + c.commits, 0);
    if (total === 0) return [];
    let cumPct = 0;
    return sorted.map((c, i) => {
      cumPct += (c.commits / total) * 100;
      return { ...c, share: Math.round((c.commits / total) * 100), cumulativePct: Math.round(cumPct), rank: i + 1 };
    }).reverse();
  }, [byContributor]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>

        <div className="space-y-6 px-4 pb-6">
          {metric === "commits" && (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{totals.commits.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Commits</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{uniqueContributors}</div>
                  <div className="text-xs text-muted-foreground">Contributors</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{avgCommitsPerDay}</div>
                  <div className="text-xs text-muted-foreground">Avg / Day</div>
                </div>
              </div>

              {commitsChartData.length > 1 && (
                <ContributionAreaChart
                  data={commitsChartData}
                  title="Commits Over Time"
                  seriesNames={{ added: "Commits" }}
                />
              )}

              {byContributor.length > 1 && (
                <ContributorTable contributors={byContributor} columns={["commits", "lines"]} />
              )}

              {byRepo.length > 1 && (
                <RepoTable repos={byRepo} columns={["commits", "lines"]} />
              )}
            </>
          )}

          {metric === "contributors" && (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{uniqueContributors}</div>
                  <div className="text-xs text-muted-foreground">Contributors</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{totals.commits.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Commits</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{activeDayCount}</div>
                  <div className="text-xs text-muted-foreground">Active Days</div>
                </div>
              </div>

              {cumulativeContributorChart.length > 1 && (
                <ContributionAreaChart
                  data={cumulativeContributorChart}
                  title="Cumulative Unique Contributors Over Time"
                  seriesNames={{ added: "Unique contributors" }}
                />
              )}

              <ContributorTable contributors={byContributor} columns={["commits", "days", "lines"]} />
            </>
          )}

          {metric === "commits_per_day" && (
            <>
              <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{avgCommitsPerDay}</div>
                  <div className="text-xs text-muted-foreground">Avg / Day</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{totals.commits.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Total Commits</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{calendarDayCount}</div>
                  <div className="text-xs text-muted-foreground">Calendar Days</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{activeDayCount}</div>
                  <div className="text-xs text-muted-foreground">Active Days</div>
                </div>
              </div>

              {chartData.length > 1 && (
                <ContributionAreaChart
                  data={commitsChartData}
                  title="Daily Commits"
                  seriesNames={{ added: "Commits" }}
                />
              )}

              {byContributor.length > 1 && (
                <ContributorTable contributors={byContributor} columns={["commits", "lines"]} />
              )}
            </>
          )}

          {metric === "bus_factor" && (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{uniqueContributors}</div>
                  <div className="text-xs text-muted-foreground">Contributors</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{totals.commits.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Commits</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">
                    {byContributor.length > 0 ? `${Math.round((byContributor[0].commits / totals.commits) * 100)}%` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground">Top Contributor %</div>
                </div>
              </div>

              <ContributorTable
                contributors={byContributor}
                columns={["commits", "share"]}
                totalCommits={totals.commits}
              />
            </>
          )}

          {metric === "churn" && (
            <>
              <div className="grid grid-cols-4 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{churnRatio}</div>
                  <div className="text-xs text-muted-foreground">Churn Ratio</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold text-emerald-500">+{totals.lines_added.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Added</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold text-red-500">-{totals.lines_deleted.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Deleted</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{(totals.lines_added - totals.lines_deleted).toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Net</div>
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                Churn ratio = lines deleted / lines added. A ratio above 1.0 means more code is being removed than added, which may indicate rework or cleanup. Low ratios suggest net growth.
              </p>

              {churnChartData.length > 1 && (
                <ContributionAreaChart
                  data={churnChartData}
                  title="Lines Added vs Deleted Over Time"
                  seriesNames={{ added: "Lines added", deleted: "Lines deleted" }}
                />
              )}

              {byContributor.length > 1 && (
                <ContributorTable contributors={byContributor} columns={["commits", "lines"]} />
              )}

              {byRepo.length > 1 && (
                <RepoTable repos={byRepo} columns={["commits", "lines"]} />
              )}
            </>
          )}

          {metric === "lines" && (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold text-emerald-500">+{totals.lines_added.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Added</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold text-red-500">-{totals.lines_deleted.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Deleted</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{(totals.lines_added - totals.lines_deleted).toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Net</div>
                </div>
              </div>

              {chartData.length > 1 && (
                <ContributionAreaChart data={chartData} title="Lines Changed Over Time" />
              )}

              {byContributor.length > 1 && (
                <ContributorTable contributors={byContributor} columns={["commits", "lines"]} />
              )}

              {byRepo.length > 1 && (
                <RepoTable repos={byRepo} columns={["commits", "lines"]} />
              )}
            </>
          )}

          {metric === "work_distribution" && (
            <>
              <p className="text-sm text-muted-foreground">
                The Gini coefficient measures how evenly commits are distributed across contributors.
                A value of <strong>0</strong> means everyone contributes equally. A value approaching <strong>1</strong> means
                a single person does nearly all the work. Values below 0.3 indicate a healthy, well-distributed team.
              </p>

              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{uniqueContributors}</div>
                  <div className="text-xs text-muted-foreground">Contributors</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{totals.commits.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Total Commits</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">
                    {byContributor.length > 0 ? `${Math.round((byContributor[0].commits / totals.commits) * 100)}%` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground">Top Contributor</div>
                </div>
              </div>

              {giniData.length > 0 && (
                <div>
                  <h4 className="mb-2 text-sm font-semibold">Commit Distribution</h4>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Contributor</TableHead>
                        <TableHead className="text-right">Commits</TableHead>
                        <TableHead className="text-right">Share</TableHead>
                        <TableHead className="text-right">Cumulative</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {giniData.map((c) => (
                        <TableRow key={c.id}>
                          <TableCell className="text-sm">{c.name}</TableCell>
                          <TableCell className="text-right tabular-nums">{c.commits.toLocaleString()}</TableCell>
                          <TableCell className="text-right tabular-nums">{c.share}%</TableCell>
                          <TableCell className="text-right tabular-nums">{c.cumulativePct}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </>
          )}

          {metric === "repos" && (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{byRepo.length}</div>
                  <div className="text-xs text-muted-foreground">Repositories</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold">{totals.commits.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Commits</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-lg font-bold text-emerald-500">+{totals.lines_added.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Lines Added</div>
                </div>
              </div>

              <RepoTable repos={byRepo} columns={["commits", "lines"]} />
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function ContributorTable({ contributors, columns, totalCommits }: {
  contributors: { id: string; name: string; commits: number; lines_added: number; lines_deleted: number; days: Set<string> }[];
  columns: ("commits" | "lines" | "days" | "share")[];
  totalCommits?: number;
}) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">By Contributor</h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Contributor</TableHead>
            {columns.includes("commits") && <TableHead className="text-right">Commits</TableHead>}
            {columns.includes("days") && <TableHead className="text-right">Active Days</TableHead>}
            {columns.includes("share") && <TableHead className="text-right">Share</TableHead>}
            {columns.includes("lines") && <TableHead className="text-right">+/-</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {contributors.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="text-sm">{c.name}</TableCell>
              {columns.includes("commits") && (
                <TableCell className="text-right tabular-nums">{c.commits.toLocaleString()}</TableCell>
              )}
              {columns.includes("days") && (
                <TableCell className="text-right tabular-nums">{c.days.size}</TableCell>
              )}
              {columns.includes("share") && totalCommits && totalCommits > 0 && (
                <TableCell className="text-right tabular-nums">
                  {Math.round((c.commits / totalCommits) * 100)}%
                </TableCell>
              )}
              {columns.includes("lines") && (
                <TableCell className="text-right text-xs">
                  <span className="text-emerald-500">+{c.lines_added.toLocaleString()}</span>
                  {" / "}
                  <span className="text-red-500">-{c.lines_deleted.toLocaleString()}</span>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function RepoTable({ repos, columns }: {
  repos: { id: string; name: string; commits: number; lines_added: number; lines_deleted: number }[];
  columns: ("commits" | "lines")[];
}) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">By Repository</h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Repository</TableHead>
            {columns.includes("commits") && <TableHead className="text-right">Commits</TableHead>}
            {columns.includes("lines") && <TableHead className="text-right">+/-</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {repos.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="text-sm">{r.name}</TableCell>
              {columns.includes("commits") && (
                <TableCell className="text-right tabular-nums">{r.commits.toLocaleString()}</TableCell>
              )}
              {columns.includes("lines") && (
                <TableCell className="text-right text-xs">
                  <span className="text-emerald-500">+{r.lines_added.toLocaleString()}</span>
                  {" / "}
                  <span className="text-red-500">-{r.lines_deleted.toLocaleString()}</span>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
