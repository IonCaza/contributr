"use client";

import Link from "next/link";
import { FolderGit2, GitCommitHorizontal, Users, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/stat-card";
import { useProjects } from "@/hooks/use-projects";
import { useTrends } from "@/hooks/use-daily-stats";

export default function DashboardPage() {
  const { data: projects = [], isLoading: loadingProjects } = useProjects();
  const { data: trends, isLoading: loadingTrends } = useTrends({});

  const loading = loadingProjects || loadingTrends;

  if (loading) {
    return <div className="animate-pulse text-muted-foreground">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Overview of all projects and contributions</p>
        </div>
        <Link href="/projects">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Projects"
          value={projects.length}
          subtitle="Across all teams"
        />
        <StatCard
          title="Commits (7d)"
          value={trends?.current_week.commits ?? 0}
          trend={trends?.wow_commits_delta}
          subtitle="Week over week"
          tooltip="Total commits across all projects in the last 7 days. The trend compares this week to last week."
        />
        <StatCard
          title="Lines Changed (7d)"
          value={(trends?.current_week.lines_added ?? 0) + (trends?.current_week.lines_deleted ?? 0)}
          trend={trends?.wow_lines_delta}
          subtitle="Added + deleted"
          tooltip="Total lines added plus lines deleted across all projects in the last 7 days"
        />
        <StatCard
          title="Avg Commits/Day"
          value={trends?.avg_commits_30d ?? 0}
          subtitle="30-day average"
          tooltip="Average number of commits per day over the last 30 days across all projects"
        />
      </div>

      <div>
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
            {projects.map((p) => (
              <Link key={p.id} href={`/projects/${p.id}`}>
                <Card className="cursor-pointer transition-colors hover:bg-accent/50">
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
