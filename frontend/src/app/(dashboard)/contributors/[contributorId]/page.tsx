"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import { Flame, GitCommitHorizontal, FileCode2, FolderGit2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatCard } from "@/components/stat-card";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { ContributorHeatmap } from "@/components/contributor-heatmap";
import { CommitList } from "@/components/commit-list";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { BranchMultiSelect } from "@/components/branch-multi-select";
import { api } from "@/lib/api-client";
import type { Contributor, ContributorStats, DailyStat, Branch, PaginatedCommits } from "@/lib/types";

export default function ContributorDetailPage() {
  const { contributorId } = useParams<{ contributorId: string }>();
  const [contributor, setContributor] = useState<Contributor | null>(null);
  const [stats, setStats] = useState<ContributorStats | null>(null);
  const [daily, setDaily] = useState<DailyStat[]>([]);
  const [repos, setRepos] = useState<{ id: string; name: string; platform: string }[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedBranches, setSelectedBranches] = useState<string[]>([]);
  const [commits, setCommits] = useState<PaginatedCommits | null>(null);
  const [commitPage, setCommitPage] = useState(1);
  const [commitsLoading, setCommitsLoading] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);

  // Stable data: contributor profile + repos (only depends on contributorId)
  useEffect(() => {
    if (!contributorId) return;
    Promise.all([
      api.getContributor(contributorId),
      api.getContributorRepos(contributorId),
    ]).then(([c, r]) => {
      setContributor(c);
      setRepos(r);
    });
  }, [contributorId]);

  // Filter-dependent data: stats + daily activity
  useEffect(() => {
    if (!contributorId) return;
    const branchParam = selectedBranches.length > 0 ? selectedBranches : undefined;
    Promise.all([
      api.getContributorStats(contributorId, {
        from_date: dateRange.from,
        to_date: dateRange.to,
        repository_id: selectedRepo || undefined,
        branch: branchParam,
      }),
      api.dailyStats({
        contributor_id: contributorId,
        from_date: dateRange.from,
        to_date: dateRange.to,
        repository_id: selectedRepo || undefined,
        branch: branchParam,
      }),
    ]).then(([s, d]) => {
      setStats(s);
      setDaily(d);
    });
  }, [contributorId, dateRange, selectedRepo, selectedBranches]);

  // Branches: scoped to the contributor within the selected repo
  useEffect(() => {
    if (selectedRepo && contributorId) {
      api.listBranches(selectedRepo, contributorId).then(setBranches);
    } else {
      setBranches([]);
      setSelectedBranches([]);
    }
  }, [selectedRepo, contributorId]);

  // Commits: depend on all filters including date range
  const fetchCommits = useCallback(async (page: number) => {
    if (!contributorId) return;
    setCommitsLoading(true);
    try {
      const data = await api.listContributorCommits(contributorId, {
        repository_id: selectedRepo || undefined,
        branch: selectedBranches.length > 0 ? selectedBranches : undefined,
        from_date: dateRange.from,
        to_date: dateRange.to,
        page,
        per_page: 30,
      });
      setCommits(data);
    } finally {
      setCommitsLoading(false);
    }
  }, [contributorId, selectedRepo, selectedBranches, dateRange]);

  useEffect(() => {
    setCommitPage(1);
    fetchCommits(1);
  }, [fetchCommits]);

  function handlePageChange(page: number) {
    setCommitPage(page);
    fetchCommits(page);
  }

  const heatmapData = useMemo(() => {
    const data: Record<string, number> = {};
    daily.forEach((d) => {
      const key = d.date.slice(0, 10);
      data[key] = (data[key] || 0) + d.commits;
    });
    return data;
  }, [daily]);

  const chartData = useMemo(() => daily.map((d) => ({
    date: d.date.slice(5),
    lines_added: d.lines_added,
    lines_deleted: d.lines_deleted,
    commits: d.commits,
  })), [daily]);

  if (!contributor || !stats) return <div className="animate-pulse text-muted-foreground">Loading contributor...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-2xl font-bold text-primary">
          {contributor.canonical_name.charAt(0).toUpperCase()}
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{contributor.canonical_name}</h1>
          <p className="text-muted-foreground">{contributor.canonical_email}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <FolderGit2 className="h-4 w-4 text-muted-foreground" />
          <Select value={selectedRepo} onValueChange={(v) => { setSelectedRepo(v === "__all__" ? "" : v); setSelectedBranches([]); }}>
            <SelectTrigger className="w-52">
              <SelectValue placeholder="All repositories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All repositories</SelectItem>
              {repos.map((r) => (
                <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {branches.length > 0 && (
          <>
            <div className="h-6 w-px bg-border" />
            <BranchMultiSelect
              branches={branches}
              selected={selectedBranches}
              onChange={setSelectedBranches}
            />
          </>
        )}
        <div className="h-6 w-px bg-border" />
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard title="Total Commits" value={stats.total_commits} trend={stats.trends.wow_commits_delta} />
        <StatCard title="Lines Added" value={stats.total_lines_added} />
        <StatCard title="Lines Deleted" value={stats.total_lines_deleted} />
        <StatCard title="Repositories" value={stats.repository_count} />
        <StatCard title="Current Streak" value={`${stats.current_streak_days}d`} subtitle="Consecutive active days" />
      </div>

      <ContributorHeatmap data={heatmapData} />

      {chartData.length > 0 ? (
        <ContributionAreaChart data={chartData} title="Activity" />
      ) : (
        <p className="text-sm text-muted-foreground">No activity data for this period.</p>
      )}

      <h2 className="text-xl font-semibold">Commits</h2>

      {commits && (
        <CommitList
          commits={commits.items}
          total={commits.total}
          page={commitPage}
          perPage={commits.per_page}
          loading={commitsLoading}
          onPageChange={handlePageChange}
          showRepo={!selectedRepo}
        />
      )}
    </div>
  );
}
