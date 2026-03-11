"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import {
  Users2, Trash2, Loader2, Search,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { StatCard } from "@/components/stat-card";
import { ProfileHeaderSkeleton, StatRowSkeleton, ChartSkeleton, TableSkeleton } from "@/components/page-skeleton";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { DateRangeFilter, defaultRange, type DateRange } from "@/components/date-range-filter";
import { ContributionAreaChart } from "@/components/charts/contribution-area-chart";
import { VelocityBarChart } from "@/components/charts/velocity-bar-chart";
import { BacklogTypeChart } from "@/components/charts/backlog-type-chart";
import { BacklogStateChart } from "@/components/charts/backlog-state-chart";
import { CycleTimeHistogram } from "@/components/charts/cycle-time-histogram";
import { WIPChart } from "@/components/charts/wip-chart";
import { BugTrendChart } from "@/components/charts/bug-trend-chart";
import { ThroughputChart } from "@/components/charts/throughput-chart";
import { TeamInsightsTab } from "@/components/team-insights-tab";

import { useTeam, useTeamMembers, useRemoveTeamMember } from "@/hooks/use-teams";
import {
  useTeamCodeStats,
  useTeamCodeActivity,
  useTeamMemberStats,
  useTeamDeliveryStats,
  useTeamDeliveryVelocity,
  useTeamDeliveryFlow,
  useTeamDeliveryBacklog,
  useTeamDeliveryQuality,
  useTeamDeliveryIntersection,
  useTeamWorkItems,
} from "@/hooks/use-team-analytics";
import { useTeamInsightsSummary } from "@/hooks/use-team-insights";

const CHART_COLORS = [
  "var(--chart-1)", "var(--chart-2)", "var(--chart-3)",
  "var(--chart-4)", "var(--chart-5)",
];

function StateTag({ state }: { state: string }) {
  const lower = state.toLowerCase();
  let cls = "bg-muted text-muted-foreground";
  if (lower.includes("active") || lower.includes("progress"))
    cls = "bg-blue-500/10 text-blue-700 dark:text-blue-400";
  else if (lower.includes("resolved") || lower.includes("done") || lower.includes("completed"))
    cls = "bg-green-500/10 text-green-700 dark:text-green-400";
  else if (lower.includes("closed"))
    cls = "bg-gray-500/10 text-gray-600 dark:text-gray-400";
  else if (lower.includes("new"))
    cls = "bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return (
    <Badge variant="secondary" className={`text-[10px] ${cls}`}>
      {state}
    </Badge>
  );
}

export default function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const [dateRange, setDateRange] = useState<DateRange>(() => defaultRange());
  const [wiSearch, setWiSearch] = useState("");
  const [wiState, setWiState] = useState<string>("all");
  const [wiPage, setWiPage] = useState(1);
  const debouncedSearch = useDebouncedValue(wiSearch);

  const { data: team, isLoading: teamLoading } = useTeam(teamId);
  const { data: members = [], isLoading: membersLoading } = useTeamMembers(teamId);
  const removeMember = useRemoveTeamMember(teamId);

  const projectId = team?.project_id ?? "";

  const { data: codeStats } = useTeamCodeStats(projectId, teamId, dateRange);
  const { data: codeActivity } = useTeamCodeActivity(projectId, teamId, dateRange);
  const { data: memberStats } = useTeamMemberStats(projectId, teamId, dateRange);

  const { data: deliveryStats } = useTeamDeliveryStats(projectId, teamId, dateRange);
  const { data: velocity } = useTeamDeliveryVelocity(projectId, teamId, dateRange);
  const { data: flow } = useTeamDeliveryFlow(projectId, teamId, dateRange);
  const { data: backlog } = useTeamDeliveryBacklog(projectId, teamId, dateRange);
  const { data: quality } = useTeamDeliveryQuality(projectId, teamId, dateRange);
  const { data: intersection } = useTeamDeliveryIntersection(projectId, teamId, dateRange);

  const { data: workItemsData } = useTeamWorkItems(projectId, teamId, {
    state: wiState === "all" ? undefined : wiState,
    search: debouncedSearch || undefined,
    page: wiPage,
    page_size: 25,
  });

  const { data: teamInsightsSummary } = useTeamInsightsSummary(projectId, teamId);
  const insightsBadgeCount = teamInsightsSummary?.total_active ?? 0;

  const completionRate = deliveryStats
    ? deliveryStats.total_work_items > 0
      ? Math.round((deliveryStats.completed_items / deliveryStats.total_work_items) * 100)
      : 0
    : 0;

  if (teamLoading) {
    return (
      <div className="space-y-6">
        <ProfileHeaderSkeleton />
        <StatRowSkeleton count={6} />
        <ChartSkeleton />
        <TableSkeleton rows={4} cols={6} />
      </div>
    );
  }

  if (!team) {
    return <div className="text-muted-foreground py-12 text-center">Team not found.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Users2 className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{team.name}</h1>
              <div className="flex items-center gap-2 mt-0.5">
                {team.platform && (
                  <Badge variant="secondary" className="text-[10px]">{team.platform}</Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {team.member_count} member{team.member_count !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
          </div>
          {team.description && (
            <p className="text-sm text-muted-foreground ml-15">{team.description}</p>
          )}
        </div>
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="code">Code</TabsTrigger>
          <TabsTrigger value="delivery">Delivery</TabsTrigger>
          <TabsTrigger value="insights">
            Insights
            {insightsBadgeCount > 0 && (
              <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5 py-0">
                {insightsBadgeCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
        </TabsList>

        {/* ── Overview Tab ────────────────────────────── */}
        <TabsContent value="overview" className="space-y-6 mt-4">
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <StatCard className={ANIM_CARD} style={stagger(0)}
              title="Total Commits"
              value={codeStats?.total_commits ?? "—"}
              tooltip="Commits by team members in the selected period"
            />
            <StatCard className={ANIM_CARD} style={stagger(1)}
              title="Story Points"
              value={deliveryStats?.completed_story_points ?? "—"}
              subtitle={deliveryStats ? `${deliveryStats.total_story_points} total` : undefined}
              tooltip="Completed story points"
            />
            <StatCard className={ANIM_CARD} style={stagger(2)}
              title="Velocity"
              value={
                deliveryStats?.velocity_trend?.length
                  ? `${deliveryStats.velocity_trend[deliveryStats.velocity_trend.length - 1].points} SP`
                  : "—"
              }
              sparklineData={deliveryStats?.velocity_trend?.map((v) => v.points)}
              tooltip="Story points completed in the most recent sprint"
            />
            <StatCard className={ANIM_CARD} style={stagger(3)}
              title="Completion Rate"
              value={`${completionRate}%`}
              tooltip="Percentage of assigned items completed"
            />
            <StatCard className={ANIM_CARD} style={stagger(4)}
              title="Avg Cycle Time"
              value={deliveryStats ? `${deliveryStats.avg_cycle_time_hours}h` : "—"}
              tooltip="Median hours from Active to Resolved"
            />
            <StatCard className={ANIM_CARD} style={stagger(5)}
              title="Active Members"
              value={memberStats?.filter((m) => m.commits > 0).length ?? team.member_count}
              subtitle={`${team.member_count} total`}
              tooltip="Members with commits in the selected period"
            />
          </div>

          {codeActivity && codeActivity.length > 0 && (
            <ContributionAreaChart data={codeActivity} title="Team Code Activity" />
          )}

          {/* Members table with code stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Team Members</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead className="text-right">Commits</TableHead>
                    <TableHead className="text-right">Lines +/-</TableHead>
                    <TableHead className="text-right">PRs</TableHead>
                    <TableHead className="text-right">Reviews</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((m) => {
                    const ms = memberStats?.find((s) => s.id === m.contributor_id);
                    return (
                      <TableRow key={m.contributor_id}>
                        <TableCell>
                          <Link href={`/contributors/${m.contributor_id}`} className="font-medium hover:underline">
                            {m.contributor_name}
                          </Link>
                          <span className="text-xs text-muted-foreground ml-2">{m.contributor_email}</span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">{m.role}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {ms?.commits?.toLocaleString() ?? "—"}
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {ms ? (
                            <>
                              <span className="text-green-600">+{ms.lines_added.toLocaleString()}</span>
                              {" / "}
                              <span className="text-red-500">-{ms.lines_deleted.toLocaleString()}</span>
                            </>
                          ) : "—"}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {ms?.prs_opened?.toLocaleString() ?? "—"}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {ms?.reviews_given?.toLocaleString() ?? "—"}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {members.length === 0 && !membersLoading && (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                        No members in this team yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Code Tab ────────────────────────────────── */}
        <TabsContent value="code" className="space-y-6 mt-4">
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <StatCard className={ANIM_CARD} style={stagger(0)} title="Total Commits" value={codeStats?.total_commits ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(1)} title="Lines Added" value={codeStats?.lines_added?.toLocaleString() ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(2)} title="Lines Deleted" value={codeStats?.lines_deleted?.toLocaleString() ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(3)} title="Active Repos" value={codeStats?.active_repos ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(4)} title="PRs Opened" value={codeStats?.prs_opened ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(5)} title="PRs Merged" value={codeStats?.prs_merged ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(6)} title="Reviews Given" value={codeStats?.reviews_given ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(7)} title="Avg Commit Size" value={codeStats?.avg_commit_size ?? "—"} subtitle="lines/commit" />
          </div>

          {codeActivity && codeActivity.length > 0 && (
            <ContributionAreaChart data={codeActivity} title="Daily Code Activity" />
          )}

          {memberStats && memberStats.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Member Contributions</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={Math.max(200, memberStats.length * 40)}>
                  <BarChart data={memberStats} layout="vertical" margin={{ left: 120, right: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="commits" name="Commits" radius={[0, 4, 4, 0]}>
                      {memberStats.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── Delivery Tab ────────────────────────────── */}
        <TabsContent value="delivery" className="space-y-6 mt-4">
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <StatCard className={ANIM_CARD} style={stagger(0)} title="Items Assigned" value={deliveryStats?.total_work_items ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(1)} title="Open Items" value={deliveryStats?.open_items ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(2)} title="Completed" value={deliveryStats?.completed_items ?? "—"} />
            <StatCard className={ANIM_CARD} style={stagger(3)} title="Completion Rate" value={`${completionRate}%`} />
            <StatCard className={ANIM_CARD} style={stagger(4)}
              title="Story Points"
              value={deliveryStats?.completed_story_points ?? "—"}
              subtitle={deliveryStats ? `${deliveryStats.total_story_points} total` : undefined}
            />
            <StatCard className={ANIM_CARD} style={stagger(5)}
              title="Avg Cycle Time"
              value={deliveryStats ? `${deliveryStats.avg_cycle_time_hours}h` : "—"}
              tooltip="Median hours from Active to Resolved"
            />
            <StatCard className={ANIM_CARD} style={stagger(6)}
              title="Avg Lead Time"
              value={deliveryStats ? `${deliveryStats.avg_lead_time_hours}h` : "—"}
              tooltip="Median hours from Created to Closed"
            />
            <StatCard className={ANIM_CARD} style={stagger(7)}
              title="Link Coverage"
              value={intersection ? `${intersection.link_coverage_pct}%` : "—"}
              tooltip="% of items with linked commits"
            />
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {velocity && velocity.length > 0 && <VelocityBarChart data={velocity} />}
            {deliveryStats?.throughput_trend && deliveryStats.throughput_trend.length > 0 && (
              <ThroughputChart data={deliveryStats.throughput_trend} />
            )}
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {deliveryStats?.backlog_by_type && deliveryStats.backlog_by_type.length > 0 && (
              <BacklogTypeChart data={deliveryStats.backlog_by_type} />
            )}
            {deliveryStats?.backlog_by_state && deliveryStats.backlog_by_state.length > 0 && (
              <BacklogStateChart data={deliveryStats.backlog_by_state} />
            )}
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {flow?.cycle_time_distribution && flow.cycle_time_distribution.length > 0 && (
              <CycleTimeHistogram data={flow.cycle_time_distribution} />
            )}
            {flow?.wip_by_state && flow.wip_by_state.length > 0 && (
              <WIPChart data={flow.wip_by_state} />
            )}
          </div>

          {quality?.bug_trend && quality.bug_trend.length > 0 && (
            <BugTrendChart data={quality.bug_trend} />
          )}

          {/* Work Items */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <CardTitle className="text-base">Work Items</CardTitle>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search by ID or title..."
                      value={wiSearch}
                      onChange={(e) => { setWiSearch(e.target.value); setWiPage(1); }}
                      className="pl-8 h-8 w-56"
                    />
                  </div>
                  <Select value={wiState} onValueChange={(v) => { setWiState(v); setWiPage(1); }}>
                    <SelectTrigger className="h-8 w-32">
                      <SelectValue placeholder="State" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All States</SelectItem>
                      <SelectItem value="New">New</SelectItem>
                      <SelectItem value="Active">Active</SelectItem>
                      <SelectItem value="Resolved">Resolved</SelectItem>
                      <SelectItem value="Closed">Closed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">ID</TableHead>
                    <TableHead className="w-20">Type</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Assigned To</TableHead>
                    <TableHead className="text-right">Points</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workItemsData?.items?.map((wi) => (
                    <TableRow key={wi.id}>
                      <TableCell className="font-mono text-xs">
                        {wi.platform_url ? (
                          <a href={wi.platform_url} target="_blank" rel="noreferrer" className="hover:underline text-primary">
                            {wi.platform_work_item_id}
                          </a>
                        ) : wi.platform_work_item_id}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">{wi.work_item_type}</Badge>
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/projects/${projectId}/delivery/work-items/${wi.id}`}
                          className="hover:underline text-sm"
                        >
                          {wi.title}
                        </Link>
                      </TableCell>
                      <TableCell><StateTag state={wi.state} /></TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {wi.assigned_to?.name ?? "—"}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {wi.story_points ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                  {(!workItemsData?.items || workItemsData.items.length === 0) && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                        No work items found
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              {workItemsData && workItemsData.total > workItemsData.page_size && (
                <div className="flex items-center justify-between px-4 py-3 border-t">
                  <span className="text-sm text-muted-foreground">
                    {workItemsData.total} items
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={wiPage <= 1}
                      onClick={() => setWiPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={wiPage * workItemsData.page_size >= workItemsData.total}
                      onClick={() => setWiPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Insights Tab ────────────────────────────── */}
        <TabsContent value="insights" className="space-y-6 mt-4">
          <TeamInsightsTab projectId={projectId} teamId={teamId} />
        </TabsContent>

        {/* ── Members Tab ─────────────────────────────── */}
        <TabsContent value="members" className="mt-4">
          {membersLoading && <div className="flex items-center gap-2 text-muted-foreground"><div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />Loading members...</div>}
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead className="w-16 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.contributor_id}>
                    <TableCell>
                      <Link href={`/contributors/${m.contributor_id}`} className="flex items-center gap-2 font-medium hover:underline">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                          {m.contributor_name.charAt(0).toUpperCase()}
                        </div>
                        {m.contributor_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{m.contributor_email}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px]">{m.role}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => removeMember.mutate(m.contributor_id)}
                        disabled={removeMember.isPending}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {members.length === 0 && !membersLoading && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                      No members in this team yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
