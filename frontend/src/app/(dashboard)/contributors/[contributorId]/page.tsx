"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { FolderGit2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatCard } from "@/components/stat-card";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { ContributorHeatmap } from "@/components/contributor-heatmap";
import { CommitList } from "@/components/commit-list";
import { StatDetailSheet } from "@/components/stat-detail-sheet";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { BranchMultiSelect } from "@/components/branch-multi-select";
import { useContributor, useContributorStats, useContributorRepos, useContributorCommits } from "@/hooks/use-contributors";
import { useRepoBranches } from "@/hooks/use-repos";
import { useDailyStats } from "@/hooks/use-daily-stats";

export default function ContributorDetailPage() {
  const { contributorId } = useParams<{ contributorId: string }>();
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [selectedBranches, setSelectedBranches] = useState<string[]>([]);
  const [commitPage, setCommitPage] = useState(1);
  const [commitSearch, setCommitSearch] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [drillDown, setDrillDown] = useState<{ title: string; metric: string } | null>(null);

  const { data: contributor } = useContributor(contributorId);
  const { data: repos = [] } = useContributorRepos(contributorId);

  const branchParam = selectedBranches.length > 0 ? selectedBranches : undefined;

  const statsFilters = useMemo(() => ({
    from_date: dateRange.from,
    to_date: dateRange.to,
    repository_id: selectedRepo || undefined,
    branch: branchParam,
  }), [dateRange, selectedRepo, branchParam]);

  const { data: stats } = useContributorStats(contributorId, statsFilters);

  const dailyParams = useMemo(() => ({
    contributor_id: contributorId,
    from_date: dateRange.from,
    to_date: dateRange.to,
    repository_id: selectedRepo || undefined,
    branch: branchParam,
  }), [contributorId, dateRange, selectedRepo, branchParam]);

  const { data: daily = [] } = useDailyStats(dailyParams);

  const { data: branches = [] } = useRepoBranches(
    selectedRepo || "",
    selectedRepo ? contributorId : undefined,
  );

  const commitFilters = useMemo(() => ({
    repository_id: selectedRepo || undefined,
    branch: branchParam,
    from_date: dateRange.from,
    to_date: dateRange.to,
    search: commitSearch || undefined,
    page: commitPage,
    per_page: 30,
  }), [selectedRepo, branchParam, dateRange, commitSearch, commitPage]);

  const { data: commits, isLoading: commitsLoading } = useContributorCommits(contributorId, commitFilters);

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
        <StatCard title="Total Commits" value={stats.total_commits} trend={stats.trends.wow_commits_delta} tooltip="Total number of commits authored in the selected time period" onClick={() => setDrillDown({ title: "Total Commits", metric: "commits" })} />
        <StatCard title="Lines Added" value={stats.total_lines_added} tooltip="Total lines of code added across all commits" onClick={() => setDrillDown({ title: "Lines Added", metric: "lines" })} />
        <StatCard title="Lines Deleted" value={stats.total_lines_deleted} tooltip="Total lines of code removed across all commits" onClick={() => setDrillDown({ title: "Lines Deleted", metric: "lines" })} />
        <StatCard title="Repositories" value={stats.repository_count} tooltip="Number of distinct repositories this contributor has committed to" onClick={() => setDrillDown({ title: "Repositories", metric: "repos" })} />
        <StatCard title="Current Streak" value={`${stats.current_streak_days}d`} subtitle="Consecutive active days" tooltip="Number of consecutive days with at least one commit, up to today" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard title="Avg Commit Size" value={`${stats.avg_commit_size} lines`} subtitle="Lines per commit" tooltip="Average number of lines changed (added + deleted) per commit. Smaller commits are generally easier to review." />
        <StatCard title="Code Velocity" value={stats.code_velocity.toLocaleString()} subtitle="Net lines (added - deleted)" tooltip="Net change in codebase size: lines added minus lines deleted. Positive means growth, negative means reduction." onClick={() => setDrillDown({ title: "Code Velocity", metric: "lines" })} />
        <StatCard title="Active Days" value={stats.active_days} subtitle="Days with commits" tooltip="Number of unique days where this contributor made at least one commit" onClick={() => setDrillDown({ title: "Active Days", metric: "commits" })} />
        <StatCard title="Impact Score" value={stats.impact_score.toLocaleString()} subtitle="Weighted contribution" tooltip="Weighted score combining commits, lines changed, PRs created, and code reviews given to measure overall contribution impact" />
        <StatCard title="Review Engagement" value={`${stats.review_engagement}x`} subtitle={`${stats.reviews_given} reviews / ${stats.prs_authored} PRs`} tooltip="Ratio of code reviews given to pull requests authored. Values above 1x mean this person reviews more code than they submit." />
      </div>

      <StatDetailSheet
        open={!!drillDown}
        onOpenChange={(v) => { if (!v) setDrillDown(null); }}
        title={drillDown?.title ?? ""}
        metric={drillDown?.metric ?? "commits"}
        daily={daily}
        contributorNames={contributor ? { [contributor.id]: contributor.canonical_name } : {}}
        repoNames={Object.fromEntries(repos.map((r) => [r.id, r.name]))}
      />

      <ContributorHeatmap data={heatmapData} />

      {chartData.length > 0 ? (
        <ContributionAreaChart data={chartData} title="Activity" />
      ) : (
        <p className="text-sm text-muted-foreground">No activity data for this period.</p>
      )}

      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">Commits</h2>
        <div className="relative w-72">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search commit messages..."
            value={commitSearch}
            onChange={(e) => { setCommitSearch(e.target.value); setCommitPage(1); }}
            className="h-8 pl-8 text-sm"
          />
        </div>
      </div>

      {commits && (
        <CommitList
          commits={commits.items}
          total={commits.total}
          page={commitPage}
          perPage={commits.per_page}
          loading={commitsLoading}
          onPageChange={setCommitPage}
          showRepo={!selectedRepo}
        />
      )}
    </div>
  );
}
