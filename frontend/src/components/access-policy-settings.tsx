"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shield, Plus, Trash2, Pencil, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";
import type { AccessPolicy, AccessPolicyCreate } from "@/lib/types";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

const ACCESS_POLICIES_KEY = ["access-policies"] as const;

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function scopeTypeBadge(scopeType: string) {
  const base = "capitalize";
  switch (scopeType) {
    case "platform":
      return <Badge className={cn(base)}>platform</Badge>;
    case "organization":
      return (
        <Badge variant="secondary" className={cn(base)}>
          organization
        </Badge>
      );
    case "team":
      return (
        <Badge variant="outline" className={cn(base, "border-sky-500/50 text-sky-700 dark:text-sky-400")}>
          team
        </Badge>
      );
    case "project":
      return (
        <Badge variant="outline" className={cn(base, "border-emerald-500/50 text-emerald-700 dark:text-emerald-400")}>
          project
        </Badge>
      );
    case "user":
      return (
        <Badge variant="outline" className={cn(base, "border-violet-500/50 text-violet-700 dark:text-violet-400")}>
          user
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className={cn(base)}>
          {scopeType}
        </Badge>
      );
  }
}

function agentRulesCount(rules: Record<string, unknown> | null): number {
  if (!rules || typeof rules !== "object") return 0;
  return Object.keys(rules).length;
}

function parseTablesInput(raw: string): string[] | null {
  const parts = raw
    .split(/[,\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length === 0) return null;
  return parts;
}

function parseAgentRulesJson(raw: string): { ok: true; value: Record<string, unknown> | null } | { ok: false; error: string } {
  const t = raw.trim();
  if (!t) return { ok: true, value: null };
  try {
    const parsed = JSON.parse(t) as unknown;
    if (parsed === null) return { ok: true, value: null };
    if (typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: "Agent/tool rules must be a JSON object." };
    }
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch {
    return { ok: false, error: "Invalid JSON for agent/tool rules." };
  }
}

export default function AccessPolicySettings() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editPolicy, setEditPolicy] = useState<AccessPolicy | null>(null);
  const [deletePolicy, setDeletePolicy] = useState<AccessPolicy | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [createScopeType, setCreateScopeType] = useState("project");
  const [createScopeId, setCreateScopeId] = useState("");
  const [createDataScope, setCreateDataScope] = useState("all");
  const [createAgentRules, setCreateAgentRules] = useState("{}");
  const [createSqlTables, setCreateSqlTables] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const [editDataScope, setEditDataScope] = useState("all");
  const [editAgentRules, setEditAgentRules] = useState("{}");
  const [editSqlTables, setEditSqlTables] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const policiesQuery = useQuery({
    queryKey: ACCESS_POLICIES_KEY,
    queryFn: () => api.listAccessPolicies(),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const rulesParsed = parseAgentRulesJson(createAgentRules);
      if (!rulesParsed.ok) throw new Error(rulesParsed.error);

      if (createScopeType !== "platform") {
        const sid = createScopeId.trim();
        if (!sid) throw new Error("Scope ID is required for this scope type.");
        if (!UUID_RE.test(sid)) throw new Error("Scope ID must be a valid UUID.");
      }

      const body: AccessPolicyCreate = {
        scope_type: createScopeType,
        scope_id: createScopeType === "platform" ? null : createScopeId.trim(),
        data_scope: createDataScope,
        agent_tool_rules: rulesParsed.value,
        sql_allowed_tables: parseTablesInput(createSqlTables),
      };
      return api.createAccessPolicy(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCESS_POLICIES_KEY });
      setCreateOpen(false);
      setCreateError(null);
      setCreateScopeType("project");
      setCreateScopeId("");
      setCreateDataScope("all");
      setCreateAgentRules("{}");
      setCreateSqlTables("");
    },
    onError: (e: unknown) => {
      setCreateError(e instanceof Error ? e.message : String(e));
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editPolicy) throw new Error("No policy selected.");
      const rulesParsed = parseAgentRulesJson(editAgentRules);
      if (!rulesParsed.ok) throw new Error(rulesParsed.error);
      return api.updateAccessPolicy(editPolicy.id, {
        data_scope: editDataScope,
        agent_tool_rules: rulesParsed.value,
        sql_allowed_tables: parseTablesInput(editSqlTables),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCESS_POLICIES_KEY });
      setEditPolicy(null);
      setEditError(null);
    },
    onError: (e: unknown) => {
      setEditError(e instanceof Error ? e.message : String(e));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteAccessPolicy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCESS_POLICIES_KEY });
      setDeletePolicy(null);
      setDeleteError(null);
    },
    onError: (e: unknown) => {
      setDeleteError(e instanceof Error ? e.message : String(e));
    },
  });

  function openEdit(p: AccessPolicy) {
    setEditPolicy(p);
    setEditDataScope(p.data_scope ?? "all");
    setEditAgentRules(
      p.agent_tool_rules && Object.keys(p.agent_tool_rules).length > 0
        ? JSON.stringify(p.agent_tool_rules, null, 2)
        : ""
    );
    setEditSqlTables(p.sql_allowed_tables?.join(", ") ?? "");
    setEditError(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Access policies
          </h2>
          <p className="text-sm text-muted-foreground">
            Define RBAC scopes, agent/tool rules, and SQL table allowlists for the platform.
          </p>
        </div>
        <Dialog
          open={createOpen}
          onOpenChange={(o) => {
            setCreateOpen(o);
            if (!o) {
              setCreateError(null);
            }
          }}
        >
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 h-4 w-4" />
              Create policy
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create access policy</DialogTitle>
            </DialogHeader>
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                setCreateError(null);
                createMutation.mutate();
              }}
            >
              <div className="space-y-2">
                <Label>Scope type</Label>
                <Select value={createScopeType} onValueChange={setCreateScopeType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="platform">platform</SelectItem>
                    <SelectItem value="organization">organization</SelectItem>
                    <SelectItem value="team">team</SelectItem>
                    <SelectItem value="project">project</SelectItem>
                    <SelectItem value="user">user</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Scope ID (UUID)</Label>
                <Input
                  value={createScopeId}
                  onChange={(e) => setCreateScopeId(e.target.value)}
                  placeholder={createScopeType === "platform" ? "Optional for platform" : "Required UUID"}
                  disabled={createScopeType === "platform"}
                  className="font-mono text-sm"
                />
                {createScopeType === "platform" && (
                  <p className="text-xs text-muted-foreground">Platform scope does not use a scope ID.</p>
                )}
              </div>
              <div className="space-y-2">
                <Label>Data scope</Label>
                <Select value={createDataScope} onValueChange={setCreateDataScope}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="own">own</SelectItem>
                    <SelectItem value="team">team</SelectItem>
                    <SelectItem value="org">org</SelectItem>
                    <SelectItem value="all">all</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Agent / tool rules (JSON object)</Label>
                <Textarea
                  value={createAgentRules}
                  onChange={(e) => setCreateAgentRules(e.target.value)}
                  className="font-mono text-xs min-h-[100px]"
                  placeholder="{}"
                />
              </div>
              <div className="space-y-2">
                <Label>SQL allowed tables</Label>
                <Textarea
                  value={createSqlTables}
                  onChange={(e) => setCreateSqlTables(e.target.value)}
                  className="font-mono text-xs min-h-[72px]"
                  placeholder="comma or newline separated, e.g. users, projects"
                />
              </div>
              {createError && <p className="text-sm text-destructive">{createError}</p>}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating…
                    </>
                  ) : (
                    "Create"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {policiesQuery.isLoading && (
        <Card>
          <CardContent className="flex items-center gap-2 py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading policies…
          </CardContent>
        </Card>
      )}

      {policiesQuery.isError && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive text-base">Could not load policies</CardTitle>
            <CardDescription>
              {policiesQuery.error instanceof Error
                ? policiesQuery.error.message
                : "Unknown error"}
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {policiesQuery.isSuccess && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Policies</CardTitle>
            <CardDescription>{policiesQuery.data.length} polic{policiesQuery.data.length === 1 ? "y" : "ies"}</CardDescription>
          </CardHeader>
          <CardContent className="min-w-0 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope type</TableHead>
                  <TableHead>Scope ID</TableHead>
                  <TableHead>Data scope</TableHead>
                  <TableHead className="text-right">Agent/Tool rules</TableHead>
                  <TableHead className="text-right">SQL tables</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {policiesQuery.data.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No access policies yet. Create one to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  policiesQuery.data.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell>{scopeTypeBadge(p.scope_type)}</TableCell>
                      <TableCell className="font-mono text-xs max-w-[200px] truncate">
                        {p.scope_id ?? "—"}
                      </TableCell>
                      <TableCell>
                        {p.data_scope ? (
                          <Badge variant="outline" className="font-normal capitalize">
                            {p.data_scope}
                          </Badge>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {agentRulesCount(p.agent_tool_rules)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {p.sql_allowed_tables?.length ?? 0}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openEdit(p)}
                            aria-label="Edit policy"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() => {
                              setDeleteError(null);
                              setDeletePolicy(p);
                            }}
                            aria-label="Delete policy"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={editPolicy != null}
        onOpenChange={(o) => {
          if (!o) {
            setEditPolicy(null);
            setEditError(null);
          }
        }}
      >
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit access policy</DialogTitle>
          </DialogHeader>
          {editPolicy && (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                setEditError(null);
                updateMutation.mutate();
              }}
            >
              <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1">
                <p>
                  <span className="text-muted-foreground">Scope type:</span>{" "}
                  {scopeTypeBadge(editPolicy.scope_type)}
                </p>
                <p className="font-mono text-xs break-all">
                  <span className="text-muted-foreground">Scope ID:</span>{" "}
                  {editPolicy.scope_id ?? "—"}
                </p>
              </div>
              <div className="space-y-2">
                <Label>Data scope</Label>
                <Select value={editDataScope} onValueChange={setEditDataScope}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="own">own</SelectItem>
                    <SelectItem value="team">team</SelectItem>
                    <SelectItem value="org">org</SelectItem>
                    <SelectItem value="all">all</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Agent / tool rules (JSON object)</Label>
                <Textarea
                  value={editAgentRules}
                  onChange={(e) => setEditAgentRules(e.target.value)}
                  className="font-mono text-xs min-h-[120px]"
                />
              </div>
              <div className="space-y-2">
                <Label>SQL allowed tables</Label>
                <Textarea
                  value={editSqlTables}
                  onChange={(e) => setEditSqlTables(e.target.value)}
                  className="font-mono text-xs min-h-[72px]"
                  placeholder="comma or newline separated"
                />
              </div>
              {editError && <p className="text-sm text-destructive">{editError}</p>}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setEditPolicy(null)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving…
                    </>
                  ) : (
                    "Save"
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deletePolicy != null}
        onOpenChange={(o) => {
          if (!o && !deleteMutation.isPending) {
            setDeletePolicy(null);
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete access policy</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-muted-foreground">
                {deletePolicy && (
                  <p>
                    Remove the policy for scope{" "}
                    <strong className="capitalize text-foreground">{deletePolicy.scope_type}</strong>
                    {deletePolicy.scope_id ? (
                      <>
                        {" "}
                        (<span className="font-mono text-xs">{deletePolicy.scope_id}</span>)
                      </>
                    ) : null}
                    ? This cannot be undone.
                  </p>
                )}
                {deleteError && <p className="text-destructive">{deleteError}</p>}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
            <Button
              type="button"
              variant="destructive"
              disabled={deleteMutation.isPending || !deletePolicy}
              onClick={() => {
                if (deletePolicy) deleteMutation.mutate(deletePolicy.id);
              }}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : (
                "Delete"
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
