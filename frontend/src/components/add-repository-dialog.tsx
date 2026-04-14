"use client";

import React, { useState, useMemo, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Link as LinkIcon, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useSSHKeys, usePlatformCredentials } from "@/hooks/use-settings";
import { useProject } from "@/hooks/use-projects";
import { useCreateRepo } from "@/hooks/use-repos";
import type { DiscoveredRepo, SSHKey, PlatformCredential } from "@/lib/types";

type WizardStep = "choose" | "byUrl" | "scanSetup" | "scanResults" | "scanCredential";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  projectId: string;
}

const INITIAL_FORM = { name: "", ssh_url: "", platform: "github", platform_owner: "", platform_repo: "", ssh_credential_id: "" };

export function AddRepositoryDialog({ open, onOpenChange, projectId }: Props) {
  const qc = useQueryClient();
  const { data: project } = useProject(projectId);
  const { data: sshKeys = [] } = useSSHKeys();
  const { data: platformCreds = [] } = usePlatformCredentials();
  const createRepo = useCreateRepo(projectId);

  const [step, setStep] = useState<WizardStep>("choose");

  // -- By URL state --
  const [repoForm, setRepoForm] = useState(INITIAL_FORM);

  // -- Scan state --
  const [scanCredentialId, setScanCredentialId] = useState("");
  const [projectName, setProjectName] = useState("");
  const [discoveredRepos, setDiscoveredRepos] = useState<DiscoveredRepo[]>([]);
  const [selectedRepos, setSelectedRepos] = useState<Set<string>>(new Set());
  const [sshKeyId, setSshKeyId] = useState("");
  const [addProgress, setAddProgress] = useState<{ done: number; total: number } | null>(null);

  const azureCreds = useMemo(
    () => platformCreds.filter((c: PlatformCredential) => c.platform === "azure"),
    [platformCreds],
  );

  const detectedAdoProject = useMemo(() => {
    if (!project) return null;
    for (const repo of project.repositories) {
      if (repo.platform === "azure" && repo.platform_owner) {
        const parts = repo.platform_owner.split("/", 2);
        return parts.length > 1 ? parts[1] : parts[0];
      }
    }
    return null;
  }, [project]);

  useEffect(() => {
    if (step === "scanSetup" && detectedAdoProject && !projectName) {
      setProjectName(detectedAdoProject);
    }
  }, [step, detectedAdoProject, projectName]);

  const discoverMutation = useMutation({
    mutationFn: () => api.discoverRepos(scanCredentialId, projectName),
    onSuccess: (repos) => {
      setDiscoveredRepos(repos);
      setSelectedRepos(new Set(repos.map((r) => r.name)));
      setStep("scanResults");
    },
  });

  function reset() {
    setStep("choose");
    setRepoForm(INITIAL_FORM);
    setScanCredentialId("");
    setProjectName("");
    setDiscoveredRepos([]);
    setSelectedRepos(new Set());
    setSshKeyId("");
    setAddProgress(null);
    discoverMutation.reset();
  }

  function handleOpenChange(v: boolean) {
    if (!v) reset();
    onOpenChange(v);
  }

  async function handleAddByUrl(e: React.FormEvent) {
    e.preventDefault();
    await createRepo.mutateAsync({ ...repoForm, ssh_credential_id: repoForm.ssh_credential_id || null });
    handleOpenChange(false);
  }

  function toggleRepo(name: string) {
    setSelectedRepos((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function toggleAll() {
    if (selectedRepos.size === discoveredRepos.length) {
      setSelectedRepos(new Set());
    } else {
      setSelectedRepos(new Set(discoveredRepos.map((r) => r.name)));
    }
  }

  async function handleBulkAdd() {
    const toAdd = discoveredRepos.filter((r) => selectedRepos.has(r.name));
    setAddProgress({ done: 0, total: toAdd.length });

    for (let i = 0; i < toAdd.length; i++) {
      const r = toAdd[i];
      await createRepo.mutateAsync({
        name: r.name,
        ssh_url: r.ssh_url || null,
        clone_url: r.remote_url || null,
        platform: "azure",
        default_branch: r.default_branch || "main",
        ssh_credential_id: sshKeyId || null,
      });
      setAddProgress({ done: i + 1, total: toAdd.length });
    }

    qc.invalidateQueries({ queryKey: queryKeys.projects.detail(projectId) });
    handleOpenChange(false);
  }

  const titles: Record<WizardStep, { title: string; description?: string }> = {
    choose: { title: "Add Repository" },
    byUrl: { title: "Add by URL", description: "Add a single repository by providing its details." },
    scanSetup: { title: "Discover Repositories", description: "Scan an Azure DevOps project to find repositories." },
    scanResults: { title: "Select Repositories", description: `${discoveredRepos.length} repositories found.` },
    scanCredential: { title: "Assign Credential", description: `Assign an SSH key to the ${selectedRepos.size} selected repositories.` },
  };

  const showBack = step !== "choose";
  const backTargets: Partial<Record<WizardStep, WizardStep>> = {
    byUrl: "choose",
    scanSetup: "choose",
    scanResults: "scanSetup",
    scanCredential: "scanResults",
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg gap-0 overflow-hidden">
        <DialogHeader className="pb-4">
          <div className="flex items-center gap-2">
            {showBack && (
              <button
                type="button"
                onClick={() => setStep(backTargets[step]!)}
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            )}
            <div>
              <DialogTitle className="text-base">{titles[step].title}</DialogTitle>
              {titles[step].description && (
                <DialogDescription className="text-xs mt-0.5">{titles[step].description}</DialogDescription>
              )}
            </div>
          </div>
        </DialogHeader>

        {/* Step 1: Choose method */}
        {step === "choose" && (
          <div className="grid grid-cols-2 gap-3 pt-1">
            <button
              onClick={() => setStep("byUrl")}
              className="flex flex-col items-center gap-2.5 rounded-lg border border-border px-4 py-5 text-center transition-colors hover:border-primary/50 hover:bg-muted/50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <LinkIcon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold">By URL</p>
                <p className="text-[11px] leading-tight text-muted-foreground mt-1">Add a single repository by SSH or HTTPS URL</p>
              </div>
            </button>
            <button
              onClick={() => setStep("scanSetup")}
              className="flex flex-col items-center gap-2.5 rounded-lg border border-border px-4 py-5 text-center transition-colors hover:border-primary/50 hover:bg-muted/50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Search className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold">Scan</p>
                <p className="text-[11px] leading-tight text-muted-foreground mt-1">Discover repositories from Azure DevOps</p>
              </div>
            </button>
          </div>
        )}

        {/* Step 2a: By URL form */}
        {step === "byUrl" && (
          <form onSubmit={handleAddByUrl} className="space-y-3 pt-1">
            <div className="space-y-1.5">
              <Label className="text-xs">Name</Label>
              <Input value={repoForm.name} onChange={(e) => setRepoForm((f) => ({ ...f, name: e.target.value }))} required />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">SSH URL</Label>
              <Input value={repoForm.ssh_url} onChange={(e) => setRepoForm((f) => ({ ...f, ssh_url: e.target.value }))} placeholder="git@github.com:org/repo.git" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Platform</Label>
                <Select value={repoForm.platform} onValueChange={(v) => setRepoForm((f) => ({ ...f, platform: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="github">GitHub</SelectItem>
                    <SelectItem value="gitlab">GitLab</SelectItem>
                    <SelectItem value="azure">Azure DevOps</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">SSH Key</Label>
                <Select value={repoForm.ssh_credential_id} onValueChange={(v) => setRepoForm((f) => ({ ...f, ssh_credential_id: v }))}>
                  <SelectTrigger><SelectValue placeholder="Select key" /></SelectTrigger>
                  <SelectContent>
                    {sshKeys.map((k: SSHKey) => (
                      <SelectItem key={k.id} value={k.id}>{k.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Owner / Org</Label>
                <Input value={repoForm.platform_owner} onChange={(e) => setRepoForm((f) => ({ ...f, platform_owner: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Repo Name</Label>
                <Input value={repoForm.platform_repo} onChange={(e) => setRepoForm((f) => ({ ...f, platform_repo: e.target.value }))} />
              </div>
            </div>
            <Button type="submit" className="w-full" disabled={createRepo.isPending}>
              {createRepo.isPending ? "Adding..." : "Add Repository"}
            </Button>
          </form>
        )}

        {/* Step 2b: Scan setup */}
        {step === "scanSetup" && (
          <div className="space-y-3 pt-1">
            <div className="space-y-1.5">
              <Label className="text-xs">Platform Token</Label>
              {azureCreds.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No Azure DevOps tokens configured. Add one in{" "}
                  <a href="/settings" className="underline text-primary">Settings &rarr; Platform Tokens</a>.
                </p>
              ) : (
                <Select value={scanCredentialId} onValueChange={setScanCredentialId}>
                  <SelectTrigger><SelectValue placeholder="Select token" /></SelectTrigger>
                  <SelectContent>
                    {azureCreds.map((c: PlatformCredential) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                        {c.base_url && <span className="text-muted-foreground ml-1 text-xs">({c.base_url})</span>}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Project Name</Label>
              <Input
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. MyAzureProject"
              />
              {detectedAdoProject && projectName === detectedAdoProject && (
                <p className="text-[11px] text-muted-foreground">Auto-detected from existing repositories.</p>
              )}
            </div>
            {discoverMutation.isError && (
              <p className="text-sm text-destructive">
                {(discoverMutation.error as Error)?.message || "Discovery failed"}
              </p>
            )}
            <Button
              className="w-full"
              disabled={!scanCredentialId || !projectName.trim() || discoverMutation.isPending}
              onClick={() => discoverMutation.mutate()}
            >
              {discoverMutation.isPending ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Discovering...</>
              ) : (
                <><Search className="mr-2 h-4 w-4" /> Discover Repositories</>
              )}
            </Button>
          </div>
        )}

        {/* Step 3: Select repos */}
        {step === "scanResults" && (
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between">
              <button onClick={toggleAll} className="text-xs font-medium text-primary hover:underline">
                {selectedRepos.size === discoveredRepos.length ? "Deselect All" : "Select All"}
              </button>
              <span className="text-xs text-muted-foreground">
                {selectedRepos.size} of {discoveredRepos.length} selected
              </span>
            </div>
            <div className="max-h-72 space-y-0.5 overflow-y-auto overflow-x-hidden rounded-md border p-1.5">
              {discoveredRepos.map((r) => (
                <label
                  key={r.name}
                  className="flex items-start gap-2.5 rounded-md px-2 py-1.5 hover:bg-muted/50 cursor-pointer"
                >
                  <Checkbox
                    checked={selectedRepos.has(r.name)}
                    onCheckedChange={() => toggleRepo(r.name)}
                    className="mt-0.5"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium leading-tight truncate">{r.name}</p>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {r.default_branch && <span className="mr-2">{r.default_branch}</span>}
                      {r.ssh_url || r.remote_url}
                    </p>
                  </div>
                </label>
              ))}
              {discoveredRepos.length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">No repositories found in this project.</p>
              )}
            </div>
            <Button
              className="w-full"
              disabled={selectedRepos.size === 0}
              onClick={() => setStep("scanCredential")}
            >
              Next
            </Button>
          </div>
        )}

        {/* Step 4: Assign SSH credential */}
        {step === "scanCredential" && (
          <div className="space-y-3 pt-1">
            <p className="text-sm text-muted-foreground">
              Adding <span className="font-semibold text-foreground">{selectedRepos.size}</span> repositor{selectedRepos.size === 1 ? "y" : "ies"} from Azure DevOps.
            </p>
            <div className="space-y-1.5">
              <Label className="text-xs">SSH Key</Label>
              <Select value={sshKeyId} onValueChange={setSshKeyId}>
                <SelectTrigger><SelectValue placeholder="Select key (optional)" /></SelectTrigger>
                <SelectContent>
                  {sshKeys.map((k: SSHKey) => (
                    <SelectItem key={k.id} value={k.id}>{k.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[11px] text-muted-foreground">
                The same SSH key will be used for all selected repositories.
              </p>
            </div>
            {addProgress ? (
              <div className="space-y-2">
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{ width: `${(addProgress.done / addProgress.total) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-center text-muted-foreground">
                  Adding {addProgress.done} of {addProgress.total}...
                </p>
              </div>
            ) : (
              <Button className="w-full" onClick={handleBulkAdd}>
                Add {selectedRepos.size} Repositor{selectedRepos.size === 1 ? "y" : "ies"}
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
