"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { FolderGit2, Search, Users } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatCard } from "@/components/stat-card";
import { ProfileHeaderSkeleton, FilterBarSkeleton, StatRowSkeleton, ChartSkeleton } from "@/components/page-skeleton";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { ContributorHeatmap } from "@/components/contributor-heatmap";
import { CommitList } from "@/components/commit-list";
import { StatDetailSheet } from "@/components/stat-detail-sheet";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { DateRangeFilter, defaultRange } from "@/components/date-range-filter";
import type { DateRange } from "@/components/date-range-filter";
import { BranchMultiSelect } from "@/components/branch-multi-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ContributorDeliveryTab } from "@/components/contributor-delivery-tab";
import { ContributorInsightsTab } from "@/components/contributor-insights-tab";
import { useContributor, useContributorStats, useContributorRepos, useContributorCommits } from "@/hooks/use-contributors";
import { useRepoBranches } from "@/hooks/use-repos";
import { useDailyStats } from "@/hooks/use-daily-stats";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

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

  useRegisterUIContext("contributor-detail", contributor && stats ? {
    contributor_id: contributorId,
    name: contributor.canonical_name,
    email: contributor.canonical_email,
    total_commits: stats.total_commits,
    total_lines_added: stats.total_lines_added,
    total_lines_deleted: stats.total_lines_deleted,
    repository_count: stats.repository_count,
    current_streak_days: stats.current_streak_days,
    avg_commit_size: stats.avg_commit_size,
    code_velocity: stats.code_velocity,
    active_days: stats.active_days,
    impact_score: stats.impact_score,
    review_engagement: stats.review_engagement,
    reviews_given: stats.reviews_given,
    prs_authored: stats.prs_authored,
  } : null);

  if (!contributor || !stats) return (
    <div className="space-y-6">
      <ProfileHeaderSkeleton />
      <FilterBarSkeleton />
      <StatRowSkeleton count={5} />
      <StatRowSkeleton count={5} />
      <ChartSkeleton />
    </div>
  );

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

      {((contributor.alias_emails && contributor.alias_emails.length > 0) ||
        (contributor.alias_names && contributor.alias_names.length > 0)) && (
        <Collapsible>
          <CollapsibleTrigger className="flex w-full items-center gap-2 rounded-lg border border-border bg-muted/30 px-4 py-2.5 text-sm hover:bg-muted/50 transition-colors">
            <Users className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">Merged Profiles</span>
            <Badge variant="secondary" className="ml-1 text-[10px]">
              {new Set([
                ...(contributor.alias_emails ?? []),
                ...(contributor.alias_names ?? []),
              ]).size}
            </Badge>
            <span className="ml-auto text-xs text-muted-foreground">Click to expand</span>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 rounded-lg border border-border bg-muted/20 px-4 py-3 space-y-2">
            {contributor.alias_names && contributor.alias_names.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground w-20 shrink-0">Names:</span>
                {contributor.alias_names.map((name) => (
                  <Badge key={name} variant="outline" className="text-xs">{name}</Badge>
                ))}
              </div>
            )}
            {contributor.alias_emails && contributor.alias_emails.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground w-20 shrink-0">Emails:</span>
                {contributor.alias_emails.map((email) => (
                  <Badge key={email} variant="outline" className="text-xs">{email}</Badge>
                ))}
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>
      )}

      <Tabs defaultValue="code" className="w-full">
        <TabsList>
          <TabsTrigger value="code">Code</TabsTrigger>
          <TabsTrigger value="delivery">Delivery</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
        </TabsList>

        <TabsContent value="code" className="space-y-6 mt-4">

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
        <StatCard className={ANIM_CARD} style={stagger(0)} title="Total Commits" value={stats.total_commits} trend={stats.trends.wow_commits_delta} tooltip="Total number of commits authored in the selected time period" onClick={() => setDrillDown({ title: "Total Commits", metric: "commits" })} />
        <StatCard className={ANIM_CARD} style={stagger(1)} title="Lines Added" value={stats.total_lines_added} tooltip="Total lines of code added across all commits" onClick={() => setDrillDown({ title: "Lines Added", metric: "lines" })} />
        <StatCard className={ANIM_CARD} style={stagger(2)} title="Lines Deleted" value={stats.total_lines_deleted} tooltip="Total lines of code removed across all commits" onClick={() => setDrillDown({ title: "Lines Deleted", metric: "lines" })} />
        <StatCard className={ANIM_CARD} style={stagger(3)} title="Repositories" value={stats.repository_count} tooltip="Number of distinct repositories this contributor has committed to" onClick={() => setDrillDown({ title: "Repositories", metric: "repos" })} />
        <StatCard className={ANIM_CARD} style={stagger(4)} title="Current Streak" value={`${stats.current_streak_days}d`} subtitle="Consecutive active days" tooltip="Number of consecutive days with at least one commit, up to today" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard className={ANIM_CARD} style={stagger(5)} title="Avg Commit Size" value={`${stats.avg_commit_size} lines`} subtitle="Lines per commit" tooltip="Average number of lines changed (added + deleted) per commit. Smaller commits are generally easier to review." />
        <StatCard className={ANIM_CARD} style={stagger(6)} title="Code Velocity" value={stats.code_velocity.toLocaleString()} subtitle="Net lines (added - deleted)" tooltip="Net change in codebase size: lines added minus lines deleted. Positive means growth, negative means reduction." onClick={() => setDrillDown({ title: "Code Velocity", metric: "lines" })} />
        <StatCard className={ANIM_CARD} style={stagger(7)} title="Active Days" value={stats.active_days} subtitle="Days with commits" tooltip="Number of unique days where this contributor made at least one commit" onClick={() => setDrillDown({ title: "Active Days", metric: "commits" })} />
        <StatCard className={ANIM_CARD} style={stagger(8)} title="Impact Score" value={stats.impact_score.toLocaleString()} subtitle="Weighted contribution" tooltip="Weighted score combining commits, lines changed, PRs created, and code reviews given to measure overall contribution impact" />
        <StatCard className={ANIM_CARD} style={stagger(9)} title="Review Engagement" value={`${stats.review_engagement}x`} subtitle={`${stats.reviews_given} reviews / ${stats.prs_authored} PRs`} tooltip="Ratio of code reviews given to pull requests authored. Values above 1x mean this person reviews more code than they submit." />
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

        </TabsContent>

        <TabsContent value="delivery" className="mt-4">
          <ContributorDeliveryTab contributorId={contributorId} contributor={contributor} />
        </TabsContent>

        <TabsContent value="insights" className="mt-4">
          <ContributorInsightsTab contributorId={contributorId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
