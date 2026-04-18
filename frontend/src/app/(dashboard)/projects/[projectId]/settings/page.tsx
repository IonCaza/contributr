"use client";

import { use, useCallback, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  GitBranch,
  LayoutDashboard,
  ShieldCheck,
  Package,
  Lightbulb,
  Loader2,
  Clock,
  Check,
  Trash2,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { DeliverySettingsSection } from "@/components/delivery/delivery-settings-section";
import { useProject, useUpdateProject, useDeleteProject, useProjectSchedule, useUpdateProjectSchedule } from "@/hooks/use-projects";

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
  const router = useRouter();
  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const updateProject = useUpdateProject(projectId);
  const deleteProject = useDeleteProject();
  const { data: schedule, isLoading } = useProjectSchedule(projectId);
  const updateSchedule = useUpdateProjectSchedule(projectId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dirty, setDirty] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    if (project) {
      setName(project.name);
      setDescription(project.description ?? "");
      setDirty(false);
    }
  }, [project]);

  function handleProjectChange(field: "name" | "description", value: string) {
    if (field === "name") setName(value);
    else setDescription(value);
    setDirty(true);
  }

  function handleProjectSave() {
    updateProject.mutate({ name: name.trim(), description: description.trim() }, {
      onSuccess: () => setDirty(false),
    });
  }

  const handleChange = useCallback(
    (key: string, value: string) => {
      updateSchedule.mutate({ [key]: value });
    },
    [updateSchedule],
  );

  if (isLoading || projectLoading) {
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
    <div className="space-y-10">
      {/* General */}
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">General</h2>
          <p className="text-sm text-muted-foreground">
            Project name and description.
          </p>
        </div>
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="project-name">Name</Label>
              <Input
                id="project-name"
                value={name}
                onChange={(e) => handleProjectChange("name", e.target.value)}
                placeholder="Project name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-description">Description</Label>
              <Input
                id="project-description"
                value={description}
                onChange={(e) => handleProjectChange("description", e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                onClick={handleProjectSave}
                disabled={!dirty || !name.trim() || updateProject.isPending}
              >
                {updateProject.isPending ? (
                  <><Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />Saving...</>
                ) : (
                  "Save"
                )}
              </Button>
              {!updateProject.isPending && updateProject.isSuccess && !dirty && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Check className="h-3.5 w-3.5" /> Saved
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Scheduling */}
      <section className="space-y-4">
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
      </section>

      {/* Delivery Analytics */}
      <DeliverySettingsSection projectId={projectId} />

      {/* Danger Zone */}
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-destructive">Danger Zone</h2>
          <p className="text-sm text-muted-foreground">
            Irreversible actions for this project.
          </p>
        </div>
        <Card className="border-destructive/30">
          <CardContent className="pt-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete this project</p>
              <p className="text-xs text-muted-foreground">
                Permanently remove this project and all its repositories, commits, and associated data.
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDelete(true)}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              Delete Project
            </Button>
          </CardContent>
        </Card>
      </section>

      <ConfirmDialog
        open={showDelete}
        onOpenChange={setShowDelete}
        title="Delete Project"
        description={<>This will permanently delete <span className="font-semibold">{project?.name}</span> and all its repositories, commits, and associated data. This action cannot be undone.</>}
        confirmLabel="Delete Project"
        expectedName={project?.name}
        expectedNameLabel="Type the project name to confirm"
        onConfirm={() => {
          deleteProject.mutate(projectId, {
            onSuccess: () => router.push("/projects"),
          });
          setShowDelete(false);
        }}
      />
    </div>
  );
}
