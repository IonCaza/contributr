"use client";

import Link from "next/link";
import { FolderGit2, GitCommitHorizontal, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/stat-card";
import { StatRowSkeleton, TableSkeleton, HeaderSkeleton } from "@/components/page-skeleton";
import { ANIM_CARD, stagger } from "@/lib/animations";
import { useProjects } from "@/hooks/use-projects";
import { useTrends, useDeliverySummary } from "@/hooks/use-daily-stats";

function formatHours(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours * 10) / 10}h`;
  const days = Math.round(hours / 24 * 10) / 10;
  return `${days}d`;
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <HeaderSkeleton />
      <StatRowSkeleton />
      <StatRowSkeleton />
      <TableSkeleton rows={3} cols={3} />
    </div>
  );
}

export default function DashboardPage() {
  const { data: projects = [], isLoading: loadingProjects } = useProjects();
  const { data: trends, isLoading: loadingTrends } = useTrends({});
  const { data: delivery, isLoading: loadingDelivery } = useDeliverySummary();

  const loading = loadingProjects || loadingTrends || loadingDelivery;

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="space-y-6">
      <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Overview of all projects and contributions</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          className={ANIM_CARD}
          style={stagger(0)}
          title="Total Projects"
          value={projects.length}
          subtitle="Across all teams"
        />
        <StatCard
          className={ANIM_CARD}
          style={stagger(1)}
          title="Commits (7d)"
          value={trends?.current_week.commits ?? 0}
          trend={trends?.wow_commits_delta}
          subtitle="Week over week"
          tooltip="Total commits across all projects in the last 7 days. The trend compares this week to last week."
        />
        <StatCard
          className={ANIM_CARD}
          style={stagger(2)}
          title="Lines Changed (7d)"
          value={(trends?.current_week.lines_added ?? 0) + (trends?.current_week.lines_deleted ?? 0)}
          trend={trends?.wow_lines_delta}
          subtitle="Added + deleted"
          tooltip="Total lines added plus lines deleted across all projects in the last 7 days"
        />
        <StatCard
          className={ANIM_CARD}
          style={stagger(3)}
          title="Active Contributors"
          value={delivery?.active_contributors_30d ?? 0}
          subtitle={`of ${delivery?.total_contributors ?? 0} total`}
          tooltip="Contributors with at least one commit in the last 30 days"
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          className={ANIM_CARD}
          style={stagger(4)}
          title="PRs Merged (7d)"
          value={delivery?.merged_prs_7d ?? 0}
          trend={delivery?.merged_prs_wow_delta}
          subtitle="Week over week"
          tooltip="Pull requests merged in the last 7 days across all repositories"
        />
        <StatCard
          className={ANIM_CARD}
          style={stagger(5)}
          title="Open PRs"
          value={delivery?.open_prs ?? 0}
          subtitle="Awaiting review or merge"
          tooltip="Total number of pull requests currently in open state across all repositories"
        />
        <StatCard
          className={ANIM_CARD}
          style={stagger(6)}
          title="PR Cycle Time"
          value={formatHours(delivery?.pr_cycle_time_hours ?? 0)}
          subtitle="Median open → merge"
          tooltip="Median time from PR creation to merge over the last 30 days. Lower is better."
        />
        <StatCard
          className={ANIM_CARD}
          style={stagger(7)}
          title="Review Turnaround"
          value={formatHours(delivery?.review_turnaround_hours ?? 0)}
          subtitle="Median to first review"
          tooltip="Median time from PR creation to first review over the last 30 days. Lower is better."
        />
      </div>

      {(delivery?.total_work_items ?? 0) > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard
            className={ANIM_CARD}
            style={stagger(8)}
            title="Open Work Items"
            value={delivery?.open_work_items ?? 0}
            subtitle={`of ${delivery?.total_work_items ?? 0} total`}
            tooltip="Work items in active states (New, Active, In Progress, etc.) across all projects"
          />
          <StatCard
            className={ANIM_CARD}
            style={stagger(9)}
            title="Completed (30d)"
            value={delivery?.completed_work_items_30d ?? 0}
            subtitle="Work items resolved"
            tooltip="Work items resolved or closed in the last 30 days across all projects"
          />
          <StatCard
            className={ANIM_CARD}
            style={stagger(10)}
            title="WI Cycle Time"
            value={formatHours(delivery?.wi_cycle_time_hours ?? 0)}
            subtitle="Median active → resolved"
            tooltip="Median time from work item activation to resolution over the last 30 days"
          />
          <StatCard
            className={ANIM_CARD}
            style={stagger(11)}
            title="Avg Commits/Day"
            value={trends?.avg_commits_30d ?? 0}
            subtitle="30-day average"
            tooltip="Average number of commits per day over the last 30 days across all projects"
          />
        </div>
      )}

      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 fill-mode-both" style={stagger(12)}>
        <h2 className="mb-4 text-xl font-semibold">Projects</h2>
        {projects.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <FolderGit2 className="mb-4 h-12 w-12 text-muted-foreground/50" />
              <p className="text-lg font-medium">No projects yet</p>
              <p className="mb-4 text-sm text-muted-foreground">Create your first project to start tracking contributions</p>
              <Link href="/projects">
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Project
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((p, i) => (
              <Link key={p.id} href={`/projects/${p.id}/code`}>
                <Card
                  className={`cursor-pointer transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-primary/30 ${ANIM_CARD}`}
                  style={stagger(i)}
                >
                  <CardHeader className="flex flex-row items-center gap-3 space-y-0 pb-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <FolderGit2 className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <CardTitle className="text-base">{p.name}</CardTitle>
                      {p.description && (
                        <p className="text-xs text-muted-foreground line-clamp-1">{p.description}</p>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <GitCommitHorizontal className="h-3 w-3" /> Repos
                      </span>
                      <Badge variant="secondary" className="text-xs">
                        {new Date(p.updated_at).toLocaleDateString()}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
