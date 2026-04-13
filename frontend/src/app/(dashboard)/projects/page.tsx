"use client";

import { useState } from "react";
import Link from "next/link";
import { FolderGit2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useProjects, useCreateProject } from "@/hooks/use-projects";

export default function ProjectsPage() {
  const { data: projects = [], isLoading } = useProjects();
  const createProject = useCreateProject();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });
  const [search, setSearch] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createProject.mutateAsync(form);
    setForm({ name: "", description: "" });
    setOpen(false);
  }

  const filtered = projects.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
        <p className="text-muted-foreground">Manage your projects and their repositories</p>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
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

      <Input placeholder="Search projects..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground"><div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />Loading...</div>
      ) : projects.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
              <FolderGit2 className="h-8 w-8 text-primary" />
            </div>
            <p className="text-lg font-semibold">No projects yet</p>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Create your first project to start tracking repositories, contributors, and delivery metrics.
            </p>
            <Button className="mt-6" onClick={() => setOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Project
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {filtered.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <FolderGit2 className="mb-4 h-12 w-12 text-muted-foreground/50" />
                <p className="text-lg font-medium">No projects match your search</p>
              </CardContent>
            </Card>
          )}
          <div className="flex flex-wrap gap-3">
            <Card
              className="group flex cursor-pointer items-center justify-center border-dashed transition-all duration-200 hover:shadow-sm hover:border-primary/50 w-52 h-52"
              onClick={() => setOpen(true)}
            >
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20">
                  <Plus className="h-5 w-5 text-primary" />
                </div>
                <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground">New Project</span>
              </div>
            </Card>
            {filtered.map((p) => (
              <Card key={p.id} className="group relative cursor-pointer transition-all duration-200 hover:shadow-sm hover:border-primary/30 w-52 h-52">
                <Link href={`/projects/${p.id}/code`} className="absolute inset-0 z-10" />
                <div className="flex flex-col items-center justify-center gap-2 px-4 py-5 h-full text-center">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                    <FolderGit2 className="h-5 w-5 text-primary" />
                  </div>
                  <div className="w-full">
                    <p className="text-sm font-semibold leading-snug truncate">{p.name}</p>
                    {p.description && <p className="text-xs leading-snug text-muted-foreground line-clamp-3 mt-1">{p.description}</p>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
