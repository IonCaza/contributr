"use client";

import { useState } from "react";
import Link from "next/link";
import { FolderGit2, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { useProjects, useCreateProject, useDeleteProject } from "@/hooks/use-projects";

export default function ProjectsPage() {
  const { data: projects = [], isLoading } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });
  const [search, setSearch] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const projectToDelete = projects.find((p) => p.id === deleteId);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createProject.mutateAsync(form);
    setForm({ name: "", description: "" });
    setOpen(false);
  }

  const filtered = projects.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">Manage your projects and their repositories</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" /> New Project</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Project</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="desc">Description</Label>
                <Input id="desc" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
              </div>
              <Button type="submit" className="w-full" disabled={createProject.isPending}>
                {createProject.isPending ? "Creating..." : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Input placeholder="Search projects..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />

      {isLoading ? (
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <FolderGit2 className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <p className="text-lg font-medium">No projects found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <Card key={p.id} className="group relative">
              <Link href={`/projects/${p.id}/code`} className="absolute inset-0 z-10" />
              <CardHeader className="flex flex-row items-center gap-3 space-y-0">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <FolderGit2 className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1">
                  <CardTitle className="text-base">{p.name}</CardTitle>
                  {p.description && <p className="text-xs text-muted-foreground line-clamp-1">{p.description}</p>}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="relative z-20 opacity-0 group-hover:opacity-100"
                  onClick={(e) => { e.preventDefault(); setDeleteId(p.id); }}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(v) => !v && setDeleteId(null)}
        title="Delete Project"
        description={<>This will permanently delete <span className="font-semibold">{projectToDelete?.name}</span> and all its repositories, commits, and associated data. This action cannot be undone.</>}
        confirmLabel="Delete Project"
        onConfirm={() => { if (deleteId) { deleteProject.mutate(deleteId); setDeleteId(null); } }}
      />
    </div>
  );
}
