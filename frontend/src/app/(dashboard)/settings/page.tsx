"use client";

import { useState, useRef } from "react";
import { Key, Users, Plus, Trash2, Copy, Check, Download, Upload, Database, Loader2, CheckCircle2, AlertCircle, Bot, Eye, EyeOff, FileX2, ShieldCheck, ShieldAlert, Play, Pencil, Cpu, Wrench, Star, ListFilter, Search, RefreshCw, CalendarRange } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api-client";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ConfirmDialog } from "@/components/confirm-dialog";
import type { LlmProvider, AgentConfig, KnowledgeGraph, DiscoveredField, SastRuleProfile } from "@/lib/types";
import { useProjects } from "@/hooks/use-projects";
import { useCustomFields, useDiscoverCustomFields, useBulkUpsertCustomFields, useDeleteCustomField } from "@/hooks/use-custom-fields";
import { KnowledgeGraphEditor } from "@/components/knowledge-graph-editor";
import {
  useSSHKeys, useCreateSSHKey, useDeleteSSHKey,
  usePlatformCredentials, useCreatePlatformCredential, useDeletePlatformCredential, useTestPlatformCredential,
  useUsers, useCreateUser, useDeleteUser,
  useFileExclusions, useCreateFileExclusion, useUpdateFileExclusion, useDeleteFileExclusion, useLoadDefaultExclusions,
  useAiSettings, useUpdateAiSettings,
  useLlmProviders, useCreateLlmProvider, useUpdateLlmProvider, useDeleteLlmProvider,
  useAgents, useCreateAgent, useUpdateAgent, useDeleteAgent,
  useAiTools,
  useKnowledgeGraphs, useKnowledgeGraph, useCreateKnowledgeGraph, useUpdateKnowledgeGraph, useDeleteKnowledgeGraph, useRegenerateKnowledgeGraph,
} from "@/hooks/use-settings";
import {
  useSastProfiles, useCreateSastProfile, useUpdateSastProfile, useDeleteSastProfile,
  useSastSettings, useUpdateSastSettings,
  useGlobalIgnoredRules, useAddGlobalIgnoredRule, useRemoveGlobalIgnoredRule,
} from "@/hooks/use-sast";

function CreateKnowledgeGraphDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [form, setForm] = useState({ name: "", description: "", generation_mode: "schema_and_entities" });
  const createKG = useCreateKnowledgeGraph();

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) setForm({ name: "", description: "", generation_mode: "schema_and_entities" }); onOpenChange(v); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create Knowledge Graph</DialogTitle>
        </DialogHeader>
        <form onSubmit={async (e) => {
          e.preventDefault();
          await createKG.mutateAsync(form);
          setForm({ name: "", description: "", generation_mode: "schema_and_entities" });
          onOpenChange(false);
        }} className="space-y-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="My Data Model" required />
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Optional description" />
          </div>
          <div className="space-y-2">
            <Label>Generation Mode</Label>
            <Select value={form.generation_mode} onValueChange={(v) => setForm((f) => ({ ...f, generation_mode: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="schema_only">Schema Only</SelectItem>
                <SelectItem value="entities_only">Entities Only</SelectItem>
                <SelectItem value="schema_and_entities">Schema + Entities</SelectItem>
                <SelectItem value="manual">Manual</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">Schema includes column names and types. Entities includes row counts.</p>
          </div>
          <Button type="submit" className="w-full" disabled={createKG.isPending}>
            {createKG.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...</> : "Create"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
    >
      {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
    </Button>
  );
}

const WELL_KNOWN_RULESETS = [
  { id: "auto", label: "Auto-detect", desc: "Detect languages and apply matching rules" },
  { id: "p/security-audit", label: "Security Audit", desc: "Comprehensive security audit rules" },
  { id: "p/owasp-top-ten", label: "OWASP Top 10", desc: "Rules mapped to OWASP Top 10 categories" },
  { id: "p/secrets", label: "Secrets", desc: "Hardcoded credentials, API keys, tokens" },
  { id: "p/python", label: "Python", desc: "Python-specific security and quality rules" },
  { id: "p/javascript", label: "JavaScript", desc: "JavaScript security rules" },
  { id: "p/typescript", label: "TypeScript", desc: "TypeScript security rules" },
  { id: "p/java", label: "Java", desc: "Java security rules" },
  { id: "p/go", label: "Go", desc: "Go security rules" },
  { id: "p/docker", label: "Docker", desc: "Dockerfile misconfigurations" },
];

function SastSettingsSection() {
  const { data: profiles = [] } = useSastProfiles();
  const { data: sastSettings } = useSastSettings();
  const createProfile = useCreateSastProfile();
  const updateProfile = useUpdateSastProfile();
  const deleteProfile = useDeleteSastProfile();
  const updateSettings = useUpdateSastSettings();
  const { data: ignoredRules = [] } = useGlobalIgnoredRules();
  const addIgnoredRule = useAddGlobalIgnoredRule();
  const removeIgnoredRule = useRemoveGlobalIgnoredRule();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<SastRuleProfile | null>(null);
  const [form, setForm] = useState({ name: "", description: "", rulesets: ["auto"] as string[], custom_rules_yaml: "", scan_branches: "" as string, is_default: false });
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [newIgnoreRule, setNewIgnoreRule] = useState("");
  const [newIgnoreReason, setNewIgnoreReason] = useState("");

  function openCreate() {
    setEditingProfile(null);
    setForm({ name: "", description: "", rulesets: ["auto"], custom_rules_yaml: "", scan_branches: "", is_default: false });
    setDialogOpen(true);
  }

  function openEdit(p: SastRuleProfile) {
    setEditingProfile(p);
    setForm({ name: p.name, description: p.description, rulesets: p.rulesets, custom_rules_yaml: p.custom_rules_yaml || "", scan_branches: p.scan_branches.join(", "), is_default: p.is_default });
    setDialogOpen(true);
  }

  async function handleSave() {
    const branchList = form.scan_branches.split(",").map((b) => b.trim()).filter(Boolean);
    const data = { ...form, custom_rules_yaml: form.custom_rules_yaml || undefined, scan_branches: branchList };
    if (editingProfile) {
      await updateProfile.mutateAsync({ id: editingProfile.id, ...data });
    } else {
      await createProfile.mutateAsync(data);
    }
    setDialogOpen(false);
  }

  function toggleRuleset(id: string) {
    setForm((f) => ({
      ...f,
      rulesets: f.rulesets.includes(id)
        ? f.rulesets.filter((r) => r !== id)
        : [...f.rulesets, id],
    }));
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Auto-Scan on Sync</CardTitle>
          <CardDescription>
            Automatically trigger a SAST scan every time a repository is synced.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Switch
              checked={sastSettings?.auto_sast_on_sync ?? false}
              onCheckedChange={(checked) => updateSettings.mutate({ auto_sast_on_sync: checked })}
            />
            <Label>Run SAST scan after every repository sync</Label>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Rule Profiles</h3>
          <p className="text-sm text-muted-foreground">
            Configure which Semgrep rulesets to apply during scans. Add custom YAML rules for project-specific checks.
          </p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" /> New Profile
        </Button>
      </div>

      {profiles.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <ShieldAlert className="h-10 w-10 mb-2" />
            <p className="font-medium">No rule profiles yet</p>
            <p className="text-sm mt-1">Create a profile to configure which rules are applied during scans.</p>
            <p className="text-sm">Without a profile, scans will use Semgrep&apos;s auto-detect mode.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {profiles.map((p) => (
            <Card key={p.id}>
              <CardContent className="flex items-center justify-between py-3 px-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{p.name}</span>
                    {p.is_default && <Badge variant="secondary" className="text-xs">Default</Badge>}
                  </div>
                  {p.description && <p className="text-xs text-muted-foreground mt-0.5">{p.description}</p>}
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {p.rulesets.map((r) => (
                      <Badge key={r} variant="outline" className="text-xs font-mono">{r}</Badge>
                    ))}
                    {p.custom_rules_yaml && <Badge variant="outline" className="text-xs">+ custom rules</Badge>}
                    {p.scan_branches.length > 0 && (
                      <Badge variant="secondary" className="text-xs">branches: {p.scan_branches.join(", ")}</Badge>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0 ml-4">
                  <Button variant="ghost" size="sm" onClick={() => openEdit(p)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleteId(p.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingProfile ? "Edit Rule Profile" : "Create Rule Profile"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="sast-name">Name</Label>
              <Input id="sast-name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Strict Security" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="sast-desc">Description</Label>
              <Input id="sast-desc" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Optional description" />
            </div>
            <div className="grid gap-2">
              <Label>Community Rulesets</Label>
              <p className="text-xs text-muted-foreground">Select which Semgrep community rulesets to include. Rules are fetched live from the Semgrep Registry at scan time.</p>
              <div className="grid gap-1.5 grid-cols-1 sm:grid-cols-2">
                {WELL_KNOWN_RULESETS.map((rs) => (
                  <button
                    key={rs.id}
                    type="button"
                    onClick={() => toggleRuleset(rs.id)}
                    className={`text-left rounded-md border p-2.5 text-sm transition-colors ${
                      form.rulesets.includes(rs.id)
                        ? "border-primary bg-primary/5"
                        : "border-muted hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`h-4 w-4 rounded border flex items-center justify-center ${
                        form.rulesets.includes(rs.id) ? "bg-primary border-primary" : "border-muted-foreground/30"
                      }`}>
                        {form.rulesets.includes(rs.id) && <Check className="h-3 w-3 text-primary-foreground" />}
                      </div>
                      <span className="font-medium">{rs.label}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 ml-6">{rs.desc}</p>
                  </button>
                ))}
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="sast-custom">Custom Rules (YAML)</Label>
              <p className="text-xs text-muted-foreground">
                Add custom Semgrep rules in YAML format. These are applied alongside the community rulesets above.
              </p>
              <Textarea
                id="sast-custom"
                value={form.custom_rules_yaml}
                onChange={(e) => setForm((f) => ({ ...f, custom_rules_yaml: e.target.value }))}
                placeholder={`rules:\n  - id: custom.no-eval\n    pattern: eval(...)\n    message: "Avoid eval()"\n    severity: ERROR\n    languages: [python]`}
                className="font-mono text-xs min-h-[160px]"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="sast-branches">Scan Branches</Label>
              <p className="text-xs text-muted-foreground">
                Comma-separated list of branch names to scan automatically (e.g. main, develop, release/*). Leave empty to scan the default branch.
              </p>
              <Input
                id="sast-branches"
                value={form.scan_branches}
                onChange={(e) => setForm((f) => ({ ...f, scan_branches: e.target.value }))}
                placeholder="main, develop"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch
                checked={form.is_default}
                onCheckedChange={(checked) => setForm((f) => ({ ...f, is_default: checked }))}
              />
              <Label>Set as default profile (used when no profile is explicitly selected)</Label>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={!form.name || form.rulesets.length === 0 || createProfile.isPending || updateProfile.isPending}>
                {(createProfile.isPending || updateProfile.isPending) && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
                {editingProfile ? "Save Changes" : "Create Profile"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(v) => !v && setDeleteId(null)}
        title="Delete Rule Profile"
        description={<>This will permanently remove the profile <span className="font-semibold">{profiles.find((p) => p.id === deleteId)?.name}</span>. Future scans will fall back to auto-detect mode.</>}
        confirmLabel="Delete Profile"
        onConfirm={() => { if (deleteId) { deleteProfile.mutate(deleteId); setDeleteId(null); } }}
      />

      {/* Ignored Rules Section */}
      <div className="flex items-center justify-between mt-6">
        <div>
          <h3 className="text-lg font-semibold">Globally Ignored Rules</h3>
          <p className="text-sm text-muted-foreground">
            Rules listed here will be excluded from all SAST scans across every repository.
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="py-4 px-4 space-y-3">
          <div className="flex gap-2">
            <Input
              value={newIgnoreRule}
              onChange={(e) => setNewIgnoreRule(e.target.value)}
              placeholder="Rule ID (e.g. python.lang.security.audit.dangerous-subprocess-use)"
              className="flex-1 font-mono text-xs"
            />
            <Input
              value={newIgnoreReason}
              onChange={(e) => setNewIgnoreReason(e.target.value)}
              placeholder="Reason (optional)"
              className="w-48"
            />
            <Button
              size="sm"
              disabled={!newIgnoreRule || addIgnoredRule.isPending}
              onClick={async () => {
                await addIgnoredRule.mutateAsync({ rule_id: newIgnoreRule, reason: newIgnoreReason });
                setNewIgnoreRule("");
                setNewIgnoreReason("");
              }}
            >
              {addIgnoredRule.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />}
              Ignore
            </Button>
          </div>

          {ignoredRules.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No globally ignored rules.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rule ID</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead className="w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ignoredRules.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">{r.rule_id}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.reason || "-"}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" className="text-destructive" onClick={() => removeIgnoredRule.mutate(r.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();

  const { data: sshKeys = [] } = useSSHKeys();
  const createSSHKey = useCreateSSHKey();
  const deleteSSHKey = useDeleteSSHKey();

  const { data: credentials = [] } = usePlatformCredentials();
  const createCredential = useCreatePlatformCredential();
  const deleteCredential = useDeletePlatformCredential();
  const testCredential = useTestPlatformCredential();

  const { data: users = [], isLoading: usersLoading } = useUsers();
  const createUser = useCreateUser();
  const deleteUser = useDeleteUser();

  const { data: exclusions = [] } = useFileExclusions();
  const createExclusion = useCreateFileExclusion();
  const updateExclusion = useUpdateFileExclusion();
  const deleteExclusion = useDeleteFileExclusion();
  const loadDefaults = useLoadDefaultExclusions();

  const { data: aiSettingsData } = useAiSettings();
  const updateAiSettings = useUpdateAiSettings();

  const { data: llmProviders = [] } = useLlmProviders();
  const createLlmProvider = useCreateLlmProvider();
  const updateLlmProvider = useUpdateLlmProvider();
  const deleteLlmProvider = useDeleteLlmProvider();

  const { data: agents = [] } = useAgents();
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent();
  const deleteAgent = useDeleteAgent();

  const { data: aiTools = [] } = useAiTools();

  const { data: knowledgeGraphs = [] } = useKnowledgeGraphs();
  const updateKG = useUpdateKnowledgeGraph();
  const deleteKG = useDeleteKnowledgeGraph();
  const regenerateKG = useRegenerateKnowledgeGraph();

  const [keyName, setKeyName] = useState("");
  const [keyType, setKeyType] = useState<"ed25519" | "rsa">("ed25519");
  const [rsaBits, setRsaBits] = useState<string>("4096");
  const [keyOpen, setKeyOpen] = useState(false);

  const [credOpen, setCredOpen] = useState(false);
  const [credForm, setCredForm] = useState({ name: "", platform: "azure", token: "", base_url: "" });
  const [credTestResult, setCredTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null);

  const [userOpen, setUserOpen] = useState(false);
  const [userForm, setUserForm] = useState({ email: "", username: "", password: "", full_name: "", is_admin: false });

  const [newPattern, setNewPattern] = useState("");
  const [newDesc, setNewDesc] = useState("");

  // LLM Provider form
  const [providerOpen, setProviderOpen] = useState(false);
  const [editProvider, setEditProvider] = useState<LlmProvider | null>(null);
  const [providerForm, setProviderForm] = useState({ name: "", provider_type: "openai", model: "", api_key: "", base_url: "", temperature: "0.1", context_window: "", is_default: false });
  const [showProviderKey, setShowProviderKey] = useState(false);

  // Agent form
  const [agentOpen, setAgentOpen] = useState(false);
  const [editAgentSlug, setEditAgentSlug] = useState<string | null>(null);
  const [agentForm, setAgentForm] = useState({ slug: "", name: "", description: "", llm_provider_id: "", system_prompt: "", max_iterations: "10", summary_token_limit: "", enabled: true, tool_slugs: [] as string[], knowledge_graph_ids: [] as string[] });

  // Knowledge Graph state
  const [kgCreateOpen, setKgCreateOpen] = useState(false);
  const [kgEditId, setKgEditId] = useState<string | null>(null);
  const { data: kgDetail } = useKnowledgeGraph(kgEditId);
  const [deleteKgId, setDeleteKgId] = useState<string | null>(null);

  // Custom Fields state
  const { data: projects = [] } = useProjects();
  const [cfProjectId, setCfProjectId] = useState<string>("");
  const { data: customFields = [] } = useCustomFields(cfProjectId || undefined);
  const discoverFields = useDiscoverCustomFields(cfProjectId || undefined);
  const bulkUpsert = useBulkUpsertCustomFields(cfProjectId || undefined);
  const deleteCustomField = useDeleteCustomField(cfProjectId || undefined);
  const [discoveredFields, setDiscoveredFields] = useState<DiscoveredField[]>([]);
  const [pendingToggles, setPendingToggles] = useState<Record<string, boolean>>({});

  const [deleteKeyId, setDeleteKeyId] = useState<string | null>(null);
  const [deleteCredId, setDeleteCredId] = useState<string | null>(null);
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [deleteProviderId, setDeleteProviderId] = useState<string | null>(null);
  const [deleteAgentSlug, setDeleteAgentSlug] = useState<string | null>(null);
  const [deleteExclusionId, setDeleteExclusionId] = useState<string | null>(null);

  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<Record<string, { submitted: number; imported: number }> | null>(null);
  const [backupError, setBackupError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [sprintScope, setSprintScope] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("contributr:sprint_scope") || "recent";
    }
    return "recent";
  });
  function handleSprintScopeChange(val: string) {
    setSprintScope(val);
    localStorage.setItem("contributr:sprint_scope", val);
  }

  async function handleCreateKey(e: React.FormEvent) {
    e.preventDefault();
    await createSSHKey.mutateAsync({
      name: keyName,
      key_type: keyType,
      ...(keyType === "rsa" ? { rsa_bits: parseInt(rsaBits) } : {}),
    });
    setKeyName("");
    setKeyType("ed25519");
    setRsaBits("4096");
    setKeyOpen(false);
  }

  async function handleCreateCredential(e: React.FormEvent) {
    e.preventDefault();
    await createCredential.mutateAsync({
      name: credForm.name,
      platform: credForm.platform,
      token: credForm.token,
      base_url: credForm.base_url || undefined,
    });
    setCredForm({ name: "", platform: "azure", token: "", base_url: "" });
    setCredOpen(false);
  }

  async function handleTestCredential(id: string) {
    setCredTestResult(null);
    try {
      const result = await testCredential.mutateAsync(id);
      setCredTestResult({ id, ...result });
    } catch {
      setCredTestResult({ id, success: false, message: "Request failed" });
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    await createUser.mutateAsync(userForm);
    setUserForm({ email: "", username: "", password: "", full_name: "", is_admin: false });
    setUserOpen(false);
  }

  async function handleToggleAi(checked?: boolean) {
    if (!aiSettingsData) return;
    const newValue = checked !== undefined ? checked : !aiSettingsData.enabled;
    await updateAiSettings.mutateAsync({ enabled: newValue });
  }

  function openProviderDialog(provider?: LlmProvider) {
    if (provider) {
      setEditProvider(provider);
      setProviderForm({
        name: provider.name,
        provider_type: provider.provider_type,
        model: provider.model,
        api_key: "",
        base_url: provider.base_url || "",
        temperature: String(provider.temperature),
        context_window: provider.context_window ? String(provider.context_window) : "",
        is_default: provider.is_default,
      });
    } else {
      setEditProvider(null);
      setProviderForm({ name: "", provider_type: "openai", model: "", api_key: "", base_url: "", temperature: "0.1", context_window: "", is_default: false });
    }
    setShowProviderKey(false);
    setProviderOpen(true);
  }

  async function handleSaveProvider(e: React.FormEvent) {
    e.preventDefault();
    const data: Record<string, unknown> = {
      name: providerForm.name,
      provider_type: providerForm.provider_type,
      model: providerForm.model,
      base_url: providerForm.base_url || "",
      temperature: parseFloat(providerForm.temperature) || 0.1,
      context_window: providerForm.context_window ? parseInt(providerForm.context_window) : null,
      is_default: providerForm.is_default,
    };
    if (providerForm.api_key) data.api_key = providerForm.api_key;

    if (editProvider) {
      await updateLlmProvider.mutateAsync({ id: editProvider.id, data: data as Parameters<typeof api.updateLlmProvider>[1] });
    } else {
      await createLlmProvider.mutateAsync(data as Parameters<typeof api.createLlmProvider>[0]);
    }
    setProviderOpen(false);
  }

  function openAgentDialog(agent?: AgentConfig) {
    if (agent) {
      setEditAgentSlug(agent.slug);
      setAgentForm({
        slug: agent.slug,
        name: agent.name,
        description: agent.description || "",
        llm_provider_id: agent.llm_provider_id || "",
        system_prompt: agent.system_prompt,
        max_iterations: String(agent.max_iterations),
        summary_token_limit: agent.summary_token_limit ? String(agent.summary_token_limit) : "",
        enabled: agent.enabled,
        tool_slugs: [...agent.tool_slugs],
        knowledge_graph_ids: [...(agent.knowledge_graph_ids || [])],
      });
    } else {
      setEditAgentSlug(null);
      setAgentForm({ slug: "", name: "", description: "", llm_provider_id: "", system_prompt: "", max_iterations: "10", summary_token_limit: "", enabled: true, tool_slugs: [], knowledge_graph_ids: [] });
    }
    setAgentOpen(true);
  }

  async function handleSaveAgent(e: React.FormEvent) {
    e.preventDefault();
    if (!agentForm.llm_provider_id) return;
    const data = {
      name: agentForm.name,
      description: agentForm.description || undefined,
      llm_provider_id: agentForm.llm_provider_id,
      system_prompt: agentForm.system_prompt,
      max_iterations: parseInt(agentForm.max_iterations) || 10,
      summary_token_limit: agentForm.summary_token_limit ? parseInt(agentForm.summary_token_limit) : null,
      enabled: agentForm.enabled,
      tool_slugs: agentForm.tool_slugs,
      knowledge_graph_ids: agentForm.knowledge_graph_ids,
    };

    if (editAgentSlug) {
      await updateAgent.mutateAsync({ slug: editAgentSlug, data });
    } else {
      await createAgent.mutateAsync({ slug: agentForm.slug, ...data });
    }
    setAgentOpen(false);
  }

  function toggleToolSlug(slug: string) {
    setAgentForm((f) => ({
      ...f,
      tool_slugs: f.tool_slugs.includes(slug)
        ? f.tool_slugs.filter((s) => s !== slug)
        : [...f.tool_slugs, slug],
    }));
  }

  async function handleExport() {
    setExporting(true);
    setBackupError(null);
    try {
      const blob = await api.exportBackup();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `contributr-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setBackupError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function handleImport(file: File) {
    setImporting(true);
    setImportResult(null);
    setBackupError(null);
    try {
      const res = await api.importBackup(file);
      setImportResult(res.counts);
    } catch (err) {
      setBackupError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage SSH keys, user accounts, and backups</p>
      </div>

      <Tabs defaultValue="ssh-keys">
        <TabsList>
          <TabsTrigger value="ssh-keys" className="gap-2"><Key className="h-4 w-4" /> SSH Keys</TabsTrigger>
          <TabsTrigger value="platform-tokens" className="gap-2"><ShieldCheck className="h-4 w-4" /> Platform Tokens</TabsTrigger>
          {user?.is_admin && <TabsTrigger value="users" className="gap-2"><Users className="h-4 w-4" /> Users</TabsTrigger>}
          {user?.is_admin && <TabsTrigger value="ai" className="gap-2"><Bot className="h-4 w-4" /> AI</TabsTrigger>}
          <TabsTrigger value="file-exclusions" className="gap-2"><FileX2 className="h-4 w-4" /> File Exclusions</TabsTrigger>
          <TabsTrigger value="custom-fields" className="gap-2"><ListFilter className="h-4 w-4" /> Custom Fields</TabsTrigger>
          <TabsTrigger value="delivery" className="gap-2"><CalendarRange className="h-4 w-4" /> Delivery</TabsTrigger>
          <TabsTrigger value="sast" className="gap-2"><ShieldAlert className="h-4 w-4" /> SAST</TabsTrigger>
          <TabsTrigger value="backup" className="gap-2"><Database className="h-4 w-4" /> Backup</TabsTrigger>
        </TabsList>

        <TabsContent value="ssh-keys" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">Generate SSH keys for repository access. Register the public key as a deploy key in your Git provider.</p>
            <Dialog open={keyOpen} onOpenChange={setKeyOpen}>
              <DialogTrigger asChild>
                <Button size="sm"><Plus className="mr-2 h-4 w-4" /> Generate Key</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Generate SSH Key</DialogTitle></DialogHeader>
                <form onSubmit={handleCreateKey} className="space-y-4">
                  <div className="space-y-2">
                    <Label>Key name</Label>
                    <Input value={keyName} onChange={(e) => setKeyName(e.target.value)} placeholder="e.g. deploy-key-prod" required />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Key type</Label>
                      <Select value={keyType} onValueChange={(v) => setKeyType(v as "ed25519" | "rsa")}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ed25519">Ed25519</SelectItem>
                          <SelectItem value="rsa">RSA</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {keyType === "rsa" && (
                      <div className="space-y-2">
                        <Label>RSA key size</Label>
                        <Select value={rsaBits} onValueChange={setRsaBits}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="2048">2048 bits</SelectItem>
                            <SelectItem value="3072">3072 bits</SelectItem>
                            <SelectItem value="4096">4096 bits</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>
                  {keyType === "ed25519" && (
                    <p className="text-xs text-muted-foreground">Ed25519 is recommended: smaller keys, faster operations, and strong security.</p>
                  )}
                  {keyType === "rsa" && (
                    <p className="text-xs text-muted-foreground">RSA is widely compatible. Use 4096 bits for best security.</p>
                  )}
                  <Button type="submit" className="w-full" disabled={createSSHKey.isPending}>
                    {createSSHKey.isPending ? "Generating..." : "Generate"}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Public Key</TableHead>
                  <TableHead>Fingerprint</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sshKeys.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-medium">{k.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono text-[10px] uppercase">{k.key_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <code className="max-w-xs truncate text-xs">{k.public_key}</code>
                        <CopyButton text={k.public_key} />
                      </div>
                    </TableCell>
                    <TableCell><code className="text-xs">{k.fingerprint}</code></TableCell>
                    <TableCell className="text-muted-foreground">{new Date(k.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteKeyId(k.id)}>
                        <Trash2 className="h-3 w-3 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {sshKeys.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">No SSH keys yet</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="platform-tokens" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">Configure API tokens (PATs) for GitHub, GitLab, or Azure DevOps to fetch PR, review, and comment data. Assign tokens to projects.</p>
            <Dialog open={credOpen} onOpenChange={setCredOpen}>
              <DialogTrigger asChild>
                <Button size="sm"><Plus className="mr-2 h-4 w-4" /> Add Token</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Add Platform Token</DialogTitle></DialogHeader>
                <form onSubmit={handleCreateCredential} className="space-y-4">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input placeholder="e.g. My Azure PAT" value={credForm.name} onChange={(e) => setCredForm((f) => ({ ...f, name: e.target.value }))} required />
                  </div>
                  <div className="space-y-2">
                    <Label>Platform</Label>
                    <Select value={credForm.platform} onValueChange={(v) => setCredForm((f) => ({ ...f, platform: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="azure">Azure DevOps</SelectItem>
                        <SelectItem value="github">GitHub</SelectItem>
                        <SelectItem value="gitlab">GitLab</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Token (PAT)</Label>
                    <Input type="password" placeholder="Paste your personal access token" value={credForm.token} onChange={(e) => setCredForm((f) => ({ ...f, token: e.target.value }))} required />
                  </div>
                  {(credForm.platform === "azure" || credForm.platform === "gitlab") && (
                    <div className="space-y-2">
                      <Label>{credForm.platform === "azure" ? "Organization URL" : "GitLab URL"}</Label>
                      <Input
                        placeholder={credForm.platform === "azure" ? "https://dev.azure.com/your-org" : "https://gitlab.com"}
                        value={credForm.base_url}
                        onChange={(e) => setCredForm((f) => ({ ...f, base_url: e.target.value }))}
                      />
                      <p className="text-xs text-muted-foreground">{credForm.platform === "azure" ? "Required for Azure DevOps." : "Leave empty for gitlab.com."}</p>
                    </div>
                  )}
                  <Button type="submit" className="w-full" disabled={createCredential.isPending}>
                    {createCredential.isPending ? "Saving..." : "Save Token"}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Base URL</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-40" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {credentials.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] uppercase">{c.platform}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{c.base_url || "-"}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(c.created_at).toLocaleDateString()}</TableCell>
                    <TableCell className="flex items-center gap-1">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7" disabled={testCredential.isPending} onClick={() => handleTestCredential(c.id)}>
                              {testCredential.isPending && testCredential.variables === c.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Test connection</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                      {credTestResult?.id === c.id && (
                        <span className={`text-xs ${credTestResult.success ? "text-emerald-500" : "text-destructive"}`}>
                          {credTestResult.success ? <CheckCircle2 className="h-3.5 w-3.5 inline mr-1" /> : <AlertCircle className="h-3.5 w-3.5 inline mr-1" />}
                          {credTestResult.message.slice(0, 60)}
                        </span>
                      )}
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteCredId(c.id)}>
                        <Trash2 className="h-3 w-3 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {credentials.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">No platform tokens configured</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {user?.is_admin && (
          <TabsContent value="users" className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Manage user accounts. Only admins can add or remove users.</p>
              <Dialog open={userOpen} onOpenChange={setUserOpen}>
                <DialogTrigger asChild>
                  <Button size="sm"><Plus className="mr-2 h-4 w-4" /> Add User</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Add User</DialogTitle></DialogHeader>
                  <form onSubmit={handleCreateUser} className="space-y-4">
                    <div className="space-y-2">
                      <Label>Full name</Label>
                      <Input value={userForm.full_name} onChange={(e) => setUserForm((f) => ({ ...f, full_name: e.target.value }))} />
                    </div>
                    <div className="space-y-2">
                      <Label>Email</Label>
                      <Input type="email" value={userForm.email} onChange={(e) => setUserForm((f) => ({ ...f, email: e.target.value }))} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Username</Label>
                      <Input value={userForm.username} onChange={(e) => setUserForm((f) => ({ ...f, username: e.target.value }))} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Password</Label>
                      <Input type="password" value={userForm.password} onChange={(e) => setUserForm((f) => ({ ...f, password: e.target.value }))} required />
                    </div>
                    <div className="flex items-center gap-2">
                      <input type="checkbox" id="is_admin" checked={userForm.is_admin} onChange={(e) => setUserForm((f) => ({ ...f, is_admin: e.target.checked }))} />
                      <Label htmlFor="is_admin">Admin privileges</Label>
                    </div>
                    <Button type="submit" className="w-full" disabled={createUser.isPending}>
                      {createUser.isPending ? "Creating..." : "Create User"}
                    </Button>
                  </form>
                </DialogContent>
              </Dialog>
            </div>

            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Username</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead className="w-20" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.username}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>{u.full_name || "-"}</TableCell>
                      <TableCell>
                        <Badge variant={u.is_admin ? "default" : "secondary"}>
                          {u.is_admin ? "Admin" : "Viewer"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {u.id !== user?.id && (
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteUserId(u.id)}>
                            <Trash2 className="h-3 w-3 text-destructive" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          </TabsContent>
        )}
        {user?.is_admin && (
          <TabsContent value="ai" className="space-y-6">
            <p className="text-sm text-muted-foreground">
              Configure LLM providers, agents, and their tools. Enable or disable the AI subsystem globally.
            </p>

            {/* Global AI Toggle */}
            {aiSettingsData && (
              <Card>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <Bot className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium">Enable AI</p>
                        <Badge variant={aiSettingsData.enabled ? "default" : "secondary"} className="text-[10px]">
                          {aiSettingsData.enabled ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Show the AI assistant to all users. Requires at least one LLM provider and one enabled agent.
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={aiSettingsData.enabled}
                    onCheckedChange={handleToggleAi}
                  />
                </CardContent>
              </Card>
            )}

            {/* LLM Providers Section */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base"><Cpu className="h-4 w-4" /> LLM Providers</CardTitle>
                  <CardDescription>Configure the language models available to your agents.</CardDescription>
                </div>
                <Button size="sm" onClick={() => openProviderDialog()}>
                  <Plus className="mr-2 h-4 w-4" /> Add Provider
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Base URL</TableHead>
                      <TableHead>API Key</TableHead>
                      <TableHead className="w-28" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {llmProviders.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {p.name}
                            {p.is_default && <Star className="h-3 w-3 text-amber-500 fill-amber-500" />}
                          </div>
                        </TableCell>
                        <TableCell><Badge variant="outline" className="text-[10px] uppercase">{p.provider_type}</Badge></TableCell>
                        <TableCell className="font-mono text-sm">{p.model}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{p.base_url || "-"}</TableCell>
                        <TableCell>
                          <Badge variant={p.has_api_key ? "default" : "secondary"} className="text-[10px]">
                            {p.has_api_key ? "Set" : "None"}
                          </Badge>
                        </TableCell>
                        <TableCell className="flex items-center gap-1">
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openProviderDialog(p)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteProviderId(p.id)}>
                            <Trash2 className="h-3 w-3 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {llmProviders.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">No LLM providers configured. Add one to get started.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* LLM Provider Dialog */}
            <Dialog open={providerOpen} onOpenChange={setProviderOpen}>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>{editProvider ? "Edit LLM Provider" : "Add LLM Provider"}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSaveProvider} className="space-y-4">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input value={providerForm.name} onChange={(e) => setProviderForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. GPT-4o, Local Ollama" required />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Provider Type</Label>
                      <Select value={providerForm.provider_type} onValueChange={(v) => setProviderForm((f) => ({ ...f, provider_type: v }))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="anthropic">Anthropic</SelectItem>
                          <SelectItem value="azure">Azure OpenAI</SelectItem>
                          <SelectItem value="ollama">Ollama</SelectItem>
                          <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Model</Label>
                      <Input value={providerForm.model} onChange={(e) => setProviderForm((f) => ({ ...f, model: e.target.value }))} placeholder="gpt-4o-mini, claude-3-sonnet..." required />
                      <p className="text-xs text-muted-foreground">LiteLLM model identifier</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>API Key</Label>
                    <div className="relative">
                      <Input
                        type={showProviderKey ? "text" : "password"}
                        value={providerForm.api_key}
                        onChange={(e) => setProviderForm((f) => ({ ...f, api_key: e.target.value }))}
                        placeholder={editProvider?.has_api_key ? "••••••• (key is set, enter new to replace)" : "sk-..."}
                      />
                      <Button type="button" variant="ghost" size="icon" className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7" onClick={() => setShowProviderKey(!showProviderKey)}>
                        {showProviderKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">Encrypted at rest. Leave blank to keep existing key.</p>
                  </div>
                  <div className="space-y-2">
                    <Label>Base URL (optional)</Label>
                    <Input value={providerForm.base_url} onChange={(e) => setProviderForm((f) => ({ ...f, base_url: e.target.value }))} placeholder="https://api.openai.com/v1" />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Temperature</Label>
                      <Input type="number" step="0.05" min="0" max="2" value={providerForm.temperature} onChange={(e) => setProviderForm((f) => ({ ...f, temperature: e.target.value }))} />
                    </div>
                    <div className="space-y-2">
                      <Label>Context Window</Label>
                      <Input type="number" min="1024" value={providerForm.context_window} onChange={(e) => setProviderForm((f) => ({ ...f, context_window: e.target.value }))} placeholder="Auto-detect" />
                      <p className="text-xs text-muted-foreground">Max input tokens. Leave blank to auto-detect.</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="checkbox" id="provider_default" checked={providerForm.is_default} onChange={(e) => setProviderForm((f) => ({ ...f, is_default: e.target.checked }))} />
                    <Label htmlFor="provider_default">Default provider for new agents</Label>
                  </div>
                  <Button type="submit" className="w-full" disabled={createLlmProvider.isPending || updateLlmProvider.isPending}>
                    {(createLlmProvider.isPending || updateLlmProvider.isPending) ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save Provider"}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>

            {/* Knowledge Graphs Section */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base"><Database className="h-4 w-4" /> Knowledge Graphs</CardTitle>
                  <CardDescription>Auto-generate data model context for agents from your database schema.</CardDescription>
                </div>
                <Button size="sm" onClick={() => setKgCreateOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" /> Add Knowledge Graph
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Mode</TableHead>
                      <TableHead>Entities</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="w-[80px]" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {knowledgeGraphs.map((kg) => (
                      <TableRow key={kg.id} className="cursor-pointer hover:bg-muted/50" onClick={() => setKgEditId(kg.id)}>
                        <TableCell className="font-medium">{kg.name}</TableCell>
                        <TableCell><Badge variant="secondary">{kg.generation_mode.replace(/_/g, " ")}</Badge></TableCell>
                        <TableCell>{kg.node_count}</TableCell>
                        <TableCell className="text-muted-foreground text-xs">{kg.updated_at.slice(0, 10)}</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={(e) => { e.stopPropagation(); setDeleteKgId(kg.id); }}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {knowledgeGraphs.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">No knowledge graphs created.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <CreateKnowledgeGraphDialog open={kgCreateOpen} onOpenChange={setKgCreateOpen} />

            {/* KG Editor Dialog */}
            <Dialog open={!!kgEditId} onOpenChange={(open) => { if (!open) setKgEditId(null); }}>
              <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Edit Knowledge Graph</DialogTitle>
                </DialogHeader>
                {kgDetail && (
                  <KnowledgeGraphEditor
                    kg={kgDetail}
                    isSaving={updateKG.isPending}
                    isRegenerating={regenerateKG.isPending}
                    onSave={(data) => updateKG.mutateAsync({ id: kgDetail.id, data })}
                    onRegenerate={() => regenerateKG.mutateAsync(kgDetail.id)}
                  />
                )}
              </DialogContent>
            </Dialog>

            <ConfirmDialog
              open={!!deleteKgId}
              onOpenChange={() => setDeleteKgId(null)}
              title="Delete Knowledge Graph"
              description="This will permanently delete this knowledge graph and remove it from any assigned agents."
              onConfirm={async () => { if (deleteKgId) { await deleteKG.mutateAsync(deleteKgId); setDeleteKgId(null); } }}
            />

            {/* Agents Section */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base"><Bot className="h-4 w-4" /> Agents</CardTitle>
                  <CardDescription>Define AI agents with custom prompts, tools, and LLM assignments.</CardDescription>
                </div>
                <Button size="sm" onClick={() => openAgentDialog()}>
                  <Plus className="mr-2 h-4 w-4" /> Add Agent
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Slug</TableHead>
                      <TableHead>LLM Provider</TableHead>
                      <TableHead>Tools</TableHead>
                      <TableHead>Enabled</TableHead>
                      <TableHead className="w-28" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {agents.map((a) => {
                      const provider = llmProviders.find((p) => p.id === a.llm_provider_id);
                      return (
                        <TableRow key={a.id}>
                          <TableCell className="font-medium">
                            <div className="flex items-center gap-2">
                              {a.name}
                              {a.is_builtin && <Badge variant="secondary" className="text-[10px]">built-in</Badge>}
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-sm text-muted-foreground">{a.slug}</TableCell>
                          <TableCell className="text-sm">{provider?.name || <span className="text-muted-foreground">None</span>}</TableCell>
                          <TableCell><Badge variant="outline" className="text-[10px]">{a.tool_slugs.length} tools</Badge></TableCell>
                          <TableCell>
                            <Switch
                              checked={a.enabled}
                              onCheckedChange={(checked) => updateAgent.mutate({ slug: a.slug, data: { enabled: checked } })}
                            />
                          </TableCell>
                          <TableCell className="flex items-center gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openAgentDialog(a)}>
                              <Pencil className="h-3 w-3" />
                            </Button>
                            {!a.is_builtin && (
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteAgentSlug(a.slug)}>
                                <Trash2 className="h-3 w-3 text-destructive" />
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                    {agents.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">No agents configured.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* Agent Dialog */}
            <Dialog open={agentOpen} onOpenChange={setAgentOpen}>
              <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>{editAgentSlug ? "Edit Agent" : "Create Agent"}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSaveAgent} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Name</Label>
                      <Input value={agentForm.name} onChange={(e) => setAgentForm((f) => ({ ...f, name: e.target.value }))} placeholder="Contribution Analyst" required />
                    </div>
                    <div className="space-y-2">
                      <Label>Slug</Label>
                      <Input value={agentForm.slug} onChange={(e) => setAgentForm((f) => ({ ...f, slug: e.target.value }))} placeholder="contribution-analyst" disabled={!!editAgentSlug} required />
                      <p className="text-xs text-muted-foreground">Unique identifier. Cannot be changed after creation.</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Description</Label>
                    <Input value={agentForm.description} onChange={(e) => setAgentForm((f) => ({ ...f, description: e.target.value }))} placeholder="What does this agent do?" />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="min-w-0 space-y-2">
                      <Label>LLM Provider <span className="text-destructive">*</span></Label>
                      <Select value={agentForm.llm_provider_id} onValueChange={(v) => setAgentForm((f) => ({ ...f, llm_provider_id: v }))}>
                        <SelectTrigger className={`w-full overflow-hidden [&>span:first-child]:truncate ${!agentForm.llm_provider_id ? "border-destructive/50" : ""}`}><SelectValue placeholder="Select a provider..." /></SelectTrigger>
                        <SelectContent>
                          {llmProviders.map((p) => (
                            <SelectItem key={p.id} value={p.id}>
                              {p.name} ({p.model})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {!agentForm.llm_provider_id && <p className="text-xs text-destructive">An LLM provider is required.</p>}
                    </div>
                    <div className="space-y-2">
                      <Label>Max Iterations</Label>
                      <Input type="number" min="1" max="999" value={agentForm.max_iterations} onChange={(e) => setAgentForm((f) => ({ ...f, max_iterations: e.target.value }))} />
                      <p className="text-xs text-muted-foreground">Max tool-calling loops.</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Summary Token Limit</Label>
                      <Input type="number" min="100" value={agentForm.summary_token_limit} onChange={(e) => setAgentForm((f) => ({ ...f, summary_token_limit: e.target.value }))} placeholder="Auto" />
                      <p className="text-xs text-muted-foreground">~4% of context window.</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>System Prompt</Label>
                    <Textarea
                      value={agentForm.system_prompt}
                      onChange={(e) => setAgentForm((f) => ({ ...f, system_prompt: e.target.value }))}
                      placeholder="You are an AI assistant that..."
                      rows={10}
                      className="font-mono text-sm"
                    />
                  </div>

                  {/* Tool Assignment */}
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2"><Wrench className="h-3.5 w-3.5" /> Assigned Tools</Label>
                    <p className="text-xs text-muted-foreground">Select which tools this agent can use. If none are selected, the agent will have access to all tools.</p>
                    <div className="grid gap-2 sm:grid-cols-2 mt-2">
                      {aiTools.map((t) => (
                        <label key={t.slug} className="flex items-start gap-2 rounded-md border p-2 cursor-pointer hover:bg-muted/50">
                          <input
                            type="checkbox"
                            checked={agentForm.tool_slugs.includes(t.slug)}
                            onChange={() => toggleToolSlug(t.slug)}
                            className="mt-0.5"
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-medium leading-tight">{t.name}</p>
                            <p className="text-xs text-muted-foreground truncate">{t.description}</p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Knowledge Graphs */}
                  {knowledgeGraphs.length > 0 && (
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2"><Database className="h-3.5 w-3.5" /> Knowledge Graphs</Label>
                      <p className="text-xs text-muted-foreground">Attach knowledge graphs to inject data model context into this agent&apos;s system prompt.</p>
                      <div className="grid gap-2 sm:grid-cols-2 mt-2">
                        {knowledgeGraphs.map((kg) => (
                          <label key={kg.id} className="flex items-start gap-2 rounded-md border p-2 cursor-pointer hover:bg-muted/50">
                            <input
                              type="checkbox"
                              checked={agentForm.knowledge_graph_ids.includes(kg.id)}
                              onChange={() => {
                                setAgentForm((f) => ({
                                  ...f,
                                  knowledge_graph_ids: f.knowledge_graph_ids.includes(kg.id)
                                    ? f.knowledge_graph_ids.filter((id) => id !== kg.id)
                                    : [...f.knowledge_graph_ids, kg.id],
                                }));
                              }}
                              className="mt-0.5"
                            />
                            <div className="min-w-0">
                              <p className="text-sm font-medium leading-tight">{kg.name}</p>
                              <p className="text-xs text-muted-foreground truncate">{kg.generation_mode.replace(/_/g, " ")} &middot; {kg.node_count} entities</p>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <Switch checked={agentForm.enabled} onCheckedChange={(checked) => setAgentForm((f) => ({ ...f, enabled: checked }))} />
                    <Label>Enabled</Label>
                  </div>
                  <Button type="submit" className="w-full" disabled={!agentForm.llm_provider_id || createAgent.isPending || updateAgent.isPending}>
                    {(createAgent.isPending || updateAgent.isPending) ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save Agent"}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </TabsContent>
        )}
        <TabsContent value="file-exclusions" className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Exclude files matching these patterns from line-count metrics during sync.
            Binary files, data files, and lock files can heavily skew contribution statistics.
            Changes take effect on the next sync — purge and re-sync existing repos to recompute metrics.
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={loadDefaults.isPending}
              onClick={() => loadDefaults.mutate()}
            >
              {loadDefaults.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Load Defaults
            </Button>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-xs text-muted-foreground cursor-help">({exclusions.filter((e) => e.enabled).length} active patterns)</span>
                </TooltipTrigger>
                <TooltipContent>Adds common patterns for binary, data, lock, and build files if not already present</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <Card>
            <CardContent className="pt-4">
              <form
                className="flex items-end gap-3"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!newPattern.trim()) return;
                  try {
                    await createExclusion.mutateAsync({ pattern: newPattern.trim(), description: newDesc.trim() || undefined });
                    setNewPattern("");
                    setNewDesc("");
                  } catch { /* ignore dups */ }
                }}
              >
                <div className="flex-1 space-y-1">
                  <Label className="text-xs">Pattern</Label>
                  <Input
                    value={newPattern}
                    onChange={(e) => setNewPattern(e.target.value)}
                    placeholder="e.g. *.csv, vendor/*, *.min.js"
                    className="font-mono text-sm"
                  />
                </div>
                <div className="flex-1 space-y-1">
                  <Label className="text-xs">Description (optional)</Label>
                  <Input
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    placeholder="e.g. Data files"
                  />
                </div>
                <Button type="submit" size="sm" disabled={!newPattern.trim() || createExclusion.isPending}>
                  <Plus className="mr-1 h-3 w-3" /> Add
                </Button>
              </form>
            </CardContent>
          </Card>

          {exclusions.length > 0 && (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">On</TableHead>
                    <TableHead>Pattern</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="w-20">Type</TableHead>
                    <TableHead className="w-10"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exclusions.map((ex) => (
                    <TableRow key={ex.id} className={!ex.enabled ? "opacity-50" : ""}>
                      <TableCell>
                        <Switch
                          checked={ex.enabled}
                          onCheckedChange={(checked) => {
                            updateExclusion.mutate({ id: ex.id, data: { enabled: checked } });
                          }}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-sm">{ex.pattern}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{ex.description || "—"}</TableCell>
                      <TableCell>
                        {ex.is_default ? (
                          <Badge variant="secondary" className="text-[10px]">default</Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px]">custom</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => setDeleteExclusionId(ex.id)}
                        >
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

        <TabsContent value="custom-fields" className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Configure which custom fields to import from Azure DevOps during work item sync.
            Discovered fields are stored per-project and included in the <code className="rounded bg-muted px-1 py-0.5 text-xs">custom_fields</code> column on each work item.
          </p>

          <div className="flex items-center gap-3">
            <Select value={cfProjectId} onValueChange={(v) => { setCfProjectId(v); setDiscoveredFields([]); setPendingToggles({}); }}>
              <SelectTrigger className="w-64">
                <SelectValue placeholder="Select a project" />
              </SelectTrigger>
              <SelectContent>
                {projects.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {cfProjectId && (
              <Button
                variant="outline"
                size="sm"
                disabled={discoverFields.isPending}
                onClick={() =>
                  discoverFields.mutate(undefined, {
                    onSuccess: (data) => {
                      setDiscoveredFields(data);
                      setPendingToggles({});
                    },
                  })
                }
              >
                {discoverFields.isPending
                  ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Discovering...</>
                  : <><Search className="mr-2 h-4 w-4" /> Discover Fields</>}
              </Button>
            )}
          </div>

          {discoverFields.isError && (
            <Card className="border-destructive">
              <CardContent className="flex items-center gap-3 pt-6">
                <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
                <p className="text-sm text-destructive">{(discoverFields.error as Error)?.message || "Failed to discover fields"}</p>
              </CardContent>
            </Card>
          )}

          {/* Configured fields for selected project */}
          {cfProjectId && customFields.length > 0 && discoveredFields.length === 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Configured Fields ({customFields.length})</CardTitle>
                <CardDescription>Fields currently imported during sync. Use &quot;Discover Fields&quot; to add more.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Field Name</TableHead>
                      <TableHead>Reference Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="w-20 text-center">Enabled</TableHead>
                      <TableHead className="w-16" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {customFields.map((cf) => (
                      <TableRow key={cf.id}>
                        <TableCell className="font-medium">{cf.display_name}</TableCell>
                        <TableCell className="text-muted-foreground text-xs font-mono">{cf.field_reference_name}</TableCell>
                        <TableCell><Badge variant="secondary" className="text-[10px]">{cf.field_type}</Badge></TableCell>
                        <TableCell className="text-center">
                          <Switch
                            checked={cf.enabled}
                            onCheckedChange={(checked) =>
                              bulkUpsert.mutate([{ field_reference_name: cf.field_reference_name, display_name: cf.display_name, field_type: cf.field_type, enabled: checked }])
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteCustomField.mutate(cf.id)}>
                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* Discovered fields table */}
          {discoveredFields.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">Available Fields ({discoveredFields.length})</CardTitle>
                    <CardDescription>Toggle fields on to import them during the next sync.</CardDescription>
                  </div>
                  <Button
                    size="sm"
                    disabled={bulkUpsert.isPending || Object.keys(pendingToggles).length === 0}
                    onClick={() => {
                      const toSave = discoveredFields
                        .filter((f) => pendingToggles[f.reference_name] !== undefined ? pendingToggles[f.reference_name] : f.is_configured)
                        .map((f) => ({
                          field_reference_name: f.reference_name,
                          display_name: f.name,
                          field_type: f.field_type,
                          enabled: true,
                        }));
                      const toDisable = discoveredFields
                        .filter((f) => f.is_configured && pendingToggles[f.reference_name] === false)
                        .map((f) => ({
                          field_reference_name: f.reference_name,
                          display_name: f.name,
                          field_type: f.field_type,
                          enabled: false,
                        }));
                      bulkUpsert.mutate([...toSave, ...toDisable], {
                        onSuccess: () => {
                          setPendingToggles({});
                          discoverFields.mutate(undefined, { onSuccess: (d) => setDiscoveredFields(d) });
                        },
                      });
                    }}
                  >
                    {bulkUpsert.isPending
                      ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</>
                      : <><RefreshCw className="mr-2 h-4 w-4" /> Save Changes</>}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16 text-center">Import</TableHead>
                      <TableHead>Field Name</TableHead>
                      <TableHead>Reference Name</TableHead>
                      <TableHead>Type</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {discoveredFields.map((f) => {
                      const checked = pendingToggles[f.reference_name] !== undefined
                        ? pendingToggles[f.reference_name]
                        : f.is_configured;
                      return (
                        <TableRow key={f.reference_name}>
                          <TableCell className="text-center">
                            <Switch
                              checked={checked}
                              onCheckedChange={(v) => setPendingToggles((prev) => ({ ...prev, [f.reference_name]: v }))}
                            />
                          </TableCell>
                          <TableCell className="font-medium">{f.name}</TableCell>
                          <TableCell className="text-muted-foreground text-xs font-mono">{f.reference_name}</TableCell>
                          <TableCell><Badge variant="secondary" className="text-[10px]">{f.field_type}</Badge></TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {cfProjectId && customFields.length === 0 && discoveredFields.length === 0 && !discoverFields.isPending && (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                No custom fields configured yet. Click &quot;Discover Fields&quot; to find available fields from Azure DevOps.
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="delivery" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Sprint Visibility</CardTitle>
              <CardDescription>
                Controls which sprints appear in the &quot;Filter Sprints&quot; and &quot;Align to Sprint&quot;
                dropdowns on the Delivery page, as well as the Iterations table.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                <Label className="shrink-0 w-36">Visible Sprints</Label>
                <Select value={sprintScope} onValueChange={handleSprintScopeChange}>
                  <SelectTrigger className="w-64">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="recent">Active + 3 past + 3 upcoming</SelectItem>
                    <SelectItem value="active_and_past">Active and past only</SelectItem>
                    <SelectItem value="all">All sprints</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground">
                This preference is stored locally in your browser and affects all projects.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sast" className="space-y-4">
          <SastSettingsSection />
        </TabsContent>

        <TabsContent value="backup" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Download className="h-4 w-4" /> Export Database
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Download a full JSON backup of all projects, repositories, contributors, commits, and other data.
                </p>
                <Button onClick={handleExport} disabled={exporting} className="w-full">
                  {exporting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Exporting...</> : <><Download className="mr-2 h-4 w-4" /> Export Backup</>}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Upload className="h-4 w-4" /> Import Database
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Restore from a JSON backup file. Existing records are preserved; only new data is added.
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleImport(f);
                  }}
                />
                <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={importing} className="w-full">
                  {importing ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Importing...</> : <><Upload className="mr-2 h-4 w-4" /> Choose Backup File</>}
                </Button>
              </CardContent>
            </Card>
          </div>

          {backupError && (
            <Card className="border-destructive">
              <CardContent className="flex items-center gap-3 pt-6">
                <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
                <p className="text-sm text-destructive">{backupError}</p>
              </CardContent>
            </Card>
          )}

          {importResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Import Complete
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Table</TableHead>
                      <TableHead className="text-right">In File</TableHead>
                      <TableHead className="text-right">Imported</TableHead>
                      <TableHead className="text-right">Skipped</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(importResult).map(([table, { submitted, imported }]) => (
                      <TableRow key={table}>
                        <TableCell className="font-medium">{table.replace(/_/g, " ")}</TableCell>
                        <TableCell className="text-right tabular-nums">{submitted.toLocaleString()}</TableCell>
                        <TableCell className="text-right tabular-nums">{imported.toLocaleString()}</TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">{(submitted - imported).toLocaleString()}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={!!deleteKeyId}
        onOpenChange={(v) => !v && setDeleteKeyId(null)}
        title="Delete SSH Key"
        description={<>This will permanently remove the SSH key <span className="font-semibold">{sshKeys.find((k) => k.id === deleteKeyId)?.name}</span>. Repositories using this key will no longer be able to authenticate.</>}
        confirmLabel="Delete Key"
        onConfirm={() => { if (deleteKeyId) { deleteSSHKey.mutate(deleteKeyId); setDeleteKeyId(null); } }}
      />

      <ConfirmDialog
        open={!!deleteCredId}
        onOpenChange={(v) => !v && setDeleteCredId(null)}
        title="Delete Platform Token"
        description={<>This will permanently remove the token <span className="font-semibold">{credentials.find((c) => c.id === deleteCredId)?.name}</span>. Projects using this token will lose access to PR and review data.</>}
        confirmLabel="Delete Token"
        onConfirm={() => { if (deleteCredId) { deleteCredential.mutate(deleteCredId); setDeleteCredId(null); } }}
      />

      <ConfirmDialog
        open={!!deleteUserId}
        onOpenChange={(v) => !v && setDeleteUserId(null)}
        title="Delete User"
        description={<>This will permanently remove <span className="font-semibold">{users.find((u) => u.id === deleteUserId)?.username}</span> and their chat history. This action cannot be undone.</>}
        confirmLabel="Delete User"
        onConfirm={() => { if (deleteUserId) { deleteUser.mutate(deleteUserId); setDeleteUserId(null); } }}
      />

      <ConfirmDialog
        open={!!deleteProviderId}
        onOpenChange={(v) => !v && setDeleteProviderId(null)}
        title="Delete LLM Provider"
        description={<>This will permanently remove <span className="font-semibold">{llmProviders.find((p) => p.id === deleteProviderId)?.name}</span>. Agents using this provider will stop working until reassigned.</>}
        confirmLabel="Delete Provider"
        onConfirm={() => { if (deleteProviderId) { deleteLlmProvider.mutate(deleteProviderId); setDeleteProviderId(null); } }}
      />

      <ConfirmDialog
        open={!!deleteAgentSlug}
        onOpenChange={(v) => !v && setDeleteAgentSlug(null)}
        title="Delete Agent"
        description={<>This will permanently remove the agent <span className="font-semibold">{agents.find((a) => a.slug === deleteAgentSlug)?.name}</span>.</>}
        confirmLabel="Delete Agent"
        onConfirm={() => { if (deleteAgentSlug) { deleteAgent.mutate(deleteAgentSlug); setDeleteAgentSlug(null); } }}
      />

      <ConfirmDialog
        open={!!deleteExclusionId}
        onOpenChange={(v) => !v && setDeleteExclusionId(null)}
        title="Remove Exclusion Pattern"
        description={<>This will remove the pattern <code className="rounded bg-muted px-1 py-0.5 text-xs">{exclusions.find((ex) => ex.id === deleteExclusionId)?.pattern}</code>. Files matching this pattern will be included in future syncs.</>}
        confirmLabel="Remove"
        onConfirm={() => { if (deleteExclusionId) { deleteExclusion.mutate(deleteExclusionId); setDeleteExclusionId(null); } }}
      />
    </div>
  );
}
