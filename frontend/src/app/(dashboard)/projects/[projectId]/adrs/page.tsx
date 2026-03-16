"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  FileText, Plus, RefreshCw, Search, Settings2, Loader2,
  Trash2, Pencil, Check, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useProject } from "@/hooks/use-projects";
import type { Adr, AdrTemplate, AdrConfig } from "@/lib/types";

const STATUS_OPTIONS = ["all", "proposed", "accepted", "deprecated", "superseded", "rejected"];

function statusColor(s: string) {
  switch (s) {
    case "proposed": return "bg-blue-500/15 text-blue-700 dark:text-blue-400";
    case "accepted": return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "deprecated": return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
    case "superseded": return "bg-purple-500/15 text-purple-700 dark:text-purple-400";
    case "rejected": return "bg-red-500/15 text-red-700 dark:text-red-400";
    default: return "bg-muted text-muted-foreground";
  }
}

export default function AdrsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const qc = useQueryClient();
  const { data: project } = useProject(projectId);

  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newTemplate, setNewTemplate] = useState("__none__");
  const [genOpen, setGenOpen] = useState(false);
  const [genText, setGenText] = useState("");
  const [configOpen, setConfigOpen] = useState(false);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [editTmpl, setEditTmpl] = useState<AdrTemplate | null>(null);
  const [tmplName, setTmplName] = useState("");
  const [tmplDesc, setTmplDesc] = useState("");
  const [tmplContent, setTmplContent] = useState("");
  const [configRepoId, setConfigRepoId] = useState("");
  const [configDir, setConfigDir] = useState("docs/adr");
  const [configNaming, setConfigNaming] = useState("{number:04d}-{slug}.md");

  const { data: config } = useQuery({
    queryKey: queryKeys.adrs.config(projectId),
    queryFn: () => api.getAdrConfig(projectId),
    enabled: !!projectId,
  });

  const { data: templates = [] } = useQuery({
    queryKey: queryKeys.adrs.templates(projectId),
    queryFn: () => api.listAdrTemplates(projectId),
    enabled: !!projectId,
  });

  const { data: adrs = [], isLoading } = useQuery({
    queryKey: queryKeys.adrs.list(projectId, { status: statusFilter, search }),
    queryFn: () => api.listAdrs(projectId, {
      status: statusFilter !== "all" ? statusFilter : undefined,
      search: search || undefined,
    }),
    enabled: !!projectId,
  });

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.adrs.list(projectId) });
    qc.invalidateQueries({ queryKey: queryKeys.adrs.config(projectId) });
    qc.invalidateQueries({ queryKey: queryKeys.adrs.templates(projectId) });
  }, [qc, projectId]);

  const createAdr = useMutation({
    mutationFn: () => api.createAdr(projectId, {
      title: newTitle,
      template_id: newTemplate !== "__none__" ? newTemplate : undefined,
    }),
    onSuccess: () => { invalidate(); setNewOpen(false); setNewTitle(""); setNewTemplate("__none__"); },
  });

  const generateAdr = useMutation({
    mutationFn: () => api.generateAdr(projectId, { text: genText }),
    onSuccess: () => { invalidate(); setGenOpen(false); setGenText(""); },
  });

  const syncAdrs = useMutation({
    mutationFn: () => api.syncAdrs(projectId),
    onSuccess: invalidate,
  });

  const saveConfig = useMutation({
    mutationFn: () => api.updateAdrConfig(projectId, {
      repository_id: configRepoId || null,
      directory_path: configDir,
      naming_convention: configNaming,
    }),
    onSuccess: () => { invalidate(); setConfigOpen(false); },
  });

  const createTemplate = useMutation({
    mutationFn: () => api.createAdrTemplate(projectId, { name: tmplName, description: tmplDesc, content: tmplContent }),
    onSuccess: () => { invalidate(); setTmplName(""); setTmplDesc(""); setTmplContent(""); },
  });

  const updateTemplate = useMutation({
    mutationFn: () => {
      if (!editTmpl) return Promise.resolve(undefined as unknown);
      return api.updateAdrTemplate(projectId, editTmpl.id, { name: tmplName, description: tmplDesc, content: tmplContent });
    },
    onSuccess: () => { invalidate(); setEditTmpl(null); },
  });

  const deleteTemplate = useMutation({
    mutationFn: (id: string) => api.deleteAdrTemplate(projectId, id),
    onSuccess: invalidate,
  });

  const deleteAdr = useMutation({
    mutationFn: (id: string) => api.deleteAdr(projectId, id),
    onSuccess: invalidate,
  });

  if (!project) return <Skeleton className="h-96" />;

  const needsConfig = !config;

  return (
    <div className="space-y-6">
      {/* Setup banner */}
      {needsConfig && (
        <Card className="border-dashed border-2">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Settings2 className="h-12 w-12 text-muted-foreground/40 mb-3" />
            <h3 className="text-lg font-medium">Configure ADR Repository</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Select a repository and directory path to store your Architecture Decision Records.
            </p>
            <Button className="mt-4" onClick={() => setConfigOpen(true)}>
              <Settings2 className="mr-2 h-4 w-4" /> Set Up ADR Storage
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Action bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-md border border-border bg-background p-0.5">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-sm capitalize transition-colors",
                statusFilter === s ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="relative ml-auto w-56">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search ADRs..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>

        <Button variant="outline" size="sm" onClick={() => syncAdrs.mutate()} disabled={syncAdrs.isPending || needsConfig}>
          {syncAdrs.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          Sync from Repo
        </Button>
        <Button variant="outline" size="sm" onClick={() => setGenOpen(true)}>
          <Sparkles className="mr-2 h-4 w-4" /> Generate with AI
        </Button>
        <Button size="sm" onClick={() => setNewOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> New ADR
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setConfigOpen(true)}>
          <Settings2 className="h-4 w-4" />
        </Button>
      </div>

      {/* ADR List */}
      <Tabs defaultValue="adrs">
        <TabsList>
          <TabsTrigger value="adrs">ADRs</TabsTrigger>
          <TabsTrigger value="templates">Templates ({templates.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="adrs" className="mt-4">
          {isLoading ? (
            <Skeleton className="h-64" />
          ) : adrs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <FileText className="h-12 w-12 text-muted-foreground/40 mb-3" />
              <h3 className="text-lg font-medium">No ADRs yet</h3>
              <p className="text-sm text-muted-foreground mt-1">Create your first Architecture Decision Record or sync from an existing repository.</p>
            </div>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">#</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>PR</TableHead>
                    <TableHead className="w-16"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {adrs.map((adr: Adr) => (
                    <TableRow key={adr.id}>
                      <TableCell className="font-mono text-muted-foreground">{adr.adr_number}</TableCell>
                      <TableCell>
                        <Link href={`/projects/${projectId}/adrs/${adr.id}`} className="font-medium hover:underline">
                          {adr.title}
                        </Link>
                        {adr.superseded_by_id && (
                          <span className="text-xs text-muted-foreground ml-2">(superseded)</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={cn("text-[10px] capitalize", statusColor(adr.status))}>
                          {adr.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(adr.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        {adr.pr_url && (
                          <a href={adr.pr_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">
                            View PR
                          </a>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => deleteAdr.mutate(adr.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="templates" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Create Template</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Name</Label>
                  <Input value={tmplName} onChange={(e) => setTmplName(e.target.value)} placeholder="My Template" />
                </div>
                <div className="space-y-1">
                  <Label>Description</Label>
                  <Input value={tmplDesc} onChange={(e) => setTmplDesc(e.target.value)} placeholder="Optional description" />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Content (Markdown)</Label>
                <Textarea value={tmplContent} onChange={(e) => setTmplContent(e.target.value)} rows={6} className="font-mono text-xs" />
              </div>
              <Button
                size="sm"
                onClick={() => editTmpl ? updateTemplate.mutate() : createTemplate.mutate()}
                disabled={!tmplName || !tmplContent}
              >
                {editTmpl ? "Update Template" : "Create Template"}
              </Button>
              {editTmpl && (
                <Button size="sm" variant="ghost" onClick={() => { setEditTmpl(null); setTmplName(""); setTmplDesc(""); setTmplContent(""); }}>
                  Cancel Edit
                </Button>
              )}
            </CardContent>
          </Card>

          {templates.map((t: AdrTemplate) => (
            <Card key={t.id} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{t.name}</span>
                    {t.is_default && <Badge variant="outline" className="text-[9px]">Default</Badge>}
                    {!t.project_id && <Badge variant="secondary" className="text-[9px]">Global</Badge>}
                  </div>
                  {t.description && <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>}
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" onClick={() => {
                    setEditTmpl(t);
                    setTmplName(t.name);
                    setTmplDesc(t.description || "");
                    setTmplContent(t.content);
                  }}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  {t.project_id && (
                    <Button variant="ghost" size="sm" className="text-destructive" onClick={() => deleteTemplate.mutate(t.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </TabsContent>
      </Tabs>

      {/* New ADR Dialog */}
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New ADR</DialogTitle>
            <DialogDescription>Enter a title and optionally select a template.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Title</Label>
              <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Use PostgreSQL for data storage" />
            </div>
            <div className="space-y-1">
              <Label>Template</Label>
              <Select value={newTemplate} onValueChange={setNewTemplate}>
                <SelectTrigger><SelectValue placeholder="No template" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Blank</SelectItem>
                  {templates.map((t: AdrTemplate) => (
                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={() => createAdr.mutate()} disabled={!newTitle || createAdr.isPending} className="w-full">
              {createAdr.isPending ? "Creating..." : "Create ADR"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Generate ADR Dialog */}
      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Generate ADR with AI</DialogTitle>
            <DialogDescription>Paste or type your decision context, and AI will structure it into an ADR.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Input Text</Label>
              <Textarea value={genText} onChange={(e) => setGenText(e.target.value)} rows={8} placeholder="We decided to use PostgreSQL instead of MongoDB because..." />
            </div>
            <Button onClick={() => generateAdr.mutate()} disabled={!genText || generateAdr.isPending} className="w-full">
              {generateAdr.isPending ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...</>
              ) : (
                <><Sparkles className="mr-2 h-4 w-4" /> Generate ADR</>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Config Dialog */}
      <Dialog open={configOpen} onOpenChange={setConfigOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ADR Configuration</DialogTitle>
            <DialogDescription>Configure the repository and directory for storing ADRs.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>Repository</Label>
              <Select value={configRepoId || (config?.repository_id ?? "")} onValueChange={setConfigRepoId}>
                <SelectTrigger><SelectValue placeholder="Select repository" /></SelectTrigger>
                <SelectContent>
                  {project?.repositories.map((r) => (
                    <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Directory Path</Label>
              <Input value={configDir} onChange={(e) => setConfigDir(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Naming Convention</Label>
              <Input value={configNaming} onChange={(e) => setConfigNaming(e.target.value)} />
              <p className="text-xs text-muted-foreground">Use {"{{number:04d}}"} and {"{{slug}}"} as placeholders.</p>
            </div>
            <Button onClick={() => saveConfig.mutate()} disabled={saveConfig.isPending} className="w-full">
              {saveConfig.isPending ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
