"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Users2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useTeams, useCreateTeam, useDeleteTeam } from "@/hooks/use-teams";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export default function TeamsPage() {
  const [projectFilter, setProjectFilter] = useState<string>("");
  const { data: teams = [], isLoading } = useTeams(projectFilter || undefined);
  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects.all,
    queryFn: () => api.listProjects(),
  });
  const createTeam = useCreateTeam();
  const deleteTeam = useDeleteTeam();

  const [createOpen, setCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [form, setForm] = useState({ project_id: "", name: "", description: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createTeam.mutateAsync({
      project_id: form.project_id,
      name: form.name,
      description: form.description || undefined,
    });
    setCreateOpen(false);
    setForm({ project_id: "", name: "", description: "" });
  }

  async function handleDelete() {
    if (!deleteId) return;
    await deleteTeam.mutateAsync(deleteId);
    setDeleteId(null);
  }

  const projectMap = Object.fromEntries(projects.map((p) => [p.id, p.name]));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Teams</h1>
          <p className="text-muted-foreground">Manage teams across projects</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={projectFilter} onValueChange={(v) => setProjectFilter(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-48"><SelectValue placeholder="All projects" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All projects</SelectItem>
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm"><Plus className="mr-2 h-4 w-4" /> Create Team</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create Team</DialogTitle></DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label>Project</Label>
                  <Select value={form.project_id} onValueChange={(v) => setForm({ ...form, project_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Select project" /></SelectTrigger>
                    <SelectContent>
                      {projects.map((p) => (
                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                </div>
                <Button type="submit" className="w-full" disabled={createTeam.isPending || !form.project_id || !form.name}>
                  {createTeam.isPending ? "Creating..." : "Create Team"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {isLoading && <p className="text-muted-foreground animate-pulse">Loading teams...</p>}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Team</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Source</TableHead>
              <TableHead className="text-right">Members</TableHead>
              <TableHead className="w-20 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {teams.map((t) => (
              <TableRow key={t.id}>
                <TableCell>
                  <Link href={`/teams/${t.id}`} className="flex items-center gap-2 font-medium hover:underline">
                    <Users2 className="h-4 w-4 text-muted-foreground" />
                    {t.name}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{projectMap[t.project_id] || "—"}</TableCell>
                <TableCell>
                  {t.platform ? (
                    <Badge variant="secondary" className="text-[10px]">{t.platform}</Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">Manual</span>
                  )}
                </TableCell>
                <TableCell className="text-right">{t.member_count}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteId(t.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {teams.length === 0 && !isLoading && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  No teams yet. Create one or sync from Azure DevOps.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      <AlertDialog open={!!deleteId} onOpenChange={(v) => !v && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Team</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete the team and remove all member associations.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
