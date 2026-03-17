"use client";

import { use, useCallback } from "react";
import {
  GitBranch,
  LayoutDashboard,
  ShieldCheck,
  Package,
  Lightbulb,
  Loader2,
  Clock,
  Check,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectSchedule, useUpdateProjectSchedule } from "@/hooks/use-projects";

const INTERVAL_OPTIONS = [
  { value: "disabled", label: "Disabled" },
  { value: "every_hour", label: "Every hour" },
  { value: "every_6_hours", label: "Every 6 hours" },
  { value: "every_12_hours", label: "Every 12 hours" },
  { value: "daily", label: "Daily" },
  { value: "every_2_days", label: "Every 2 days" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
] as const;

const SCHEDULE_FIELDS = [
  {
    key: "repo_sync_interval" as const,
    lastRunKey: "repo_sync_last_run_at" as const,
    label: "Repository Sync",
    description: "Clone/fetch all repositories, extract commits, fetch PRs and reviews, and rebuild contributor stats.",
    icon: GitBranch,
  },
  {
    key: "delivery_sync_interval" as const,
    lastRunKey: "delivery_sync_last_run_at" as const,
    label: "Azure DevOps Sync",
    description: "Sync teams, iterations, work items, and activity history from Azure DevOps.",
    icon: LayoutDashboard,
  },
  {
    key: "security_scan_interval" as const,
    lastRunKey: "security_scan_last_run_at" as const,
    label: "Security Scans",
    description: "Run SAST analysis (Semgrep) on all repositories to detect security vulnerabilities.",
    icon: ShieldCheck,
  },
  {
    key: "dependency_scan_interval" as const,
    lastRunKey: "dependency_scan_last_run_at" as const,
    label: "Dependency Scans",
    description: "Scan dependency manifests for known vulnerabilities and outdated packages.",
    icon: Package,
  },
  {
    key: "insights_interval" as const,
    lastRunKey: "insights_last_run_at" as const,
    label: "Insights Generation",
    description: "Analyze project health, team balance, code quality, and delivery efficiency.",
    icon: Lightbulb,
  },
] as const;

function formatLastRun(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function ProjectSettingsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const { data: schedule, isLoading } = useProjectSchedule(projectId);
  const updateSchedule = useUpdateProjectSchedule(projectId);

  const handleChange = useCallback(
    (key: string, value: string) => {
      updateSchedule.mutate({ [key]: value });
    },
    [updateSchedule],
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-5 w-72 mt-1" />
        </div>
        <div className="grid gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Scheduling</h2>
          <p className="text-sm text-muted-foreground">
            Configure how often automated tasks run for this project.
          </p>
        </div>
        {updateSchedule.isPending && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Saving...</span>
          </div>
        )}
        {!updateSchedule.isPending && updateSchedule.isSuccess && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Check className="h-3.5 w-3.5" />
            <span>Saved</span>
          </div>
        )}
      </div>

      <div className="grid gap-4">
        {SCHEDULE_FIELDS.map((field) => {
          const Icon = field.icon;
          const lastRun = schedule?.[field.lastRunKey] ?? null;
          const currentValue = schedule?.[field.key] ?? "disabled";
          return (
            <Card key={field.key}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-muted">
                      <Icon className="h-4.5 w-4.5 text-muted-foreground" />
                    </div>
                    <div>
                      <CardTitle className="text-base">{field.label}</CardTitle>
                      <CardDescription className="text-xs mt-0.5">
                        {field.description}
                      </CardDescription>
                    </div>
                  </div>
                  <Select
                    value={currentValue}
                    onValueChange={(v) => handleChange(field.key, v)}
                    disabled={updateSchedule.isPending}
                  >
                    <SelectTrigger className="w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {INTERVAL_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>Last run: {formatLastRun(lastRun)}</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
