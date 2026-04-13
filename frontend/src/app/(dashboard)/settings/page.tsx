"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Key, Users, Plus, Trash2, Copy, Check, Download, Upload, Database, Loader2, CheckCircle2, AlertCircle, Bot, Eye, EyeOff, FileX2, ShieldCheck, ShieldAlert, Play, Pencil, Cpu, Star, ListFilter, Search, RefreshCw, CalendarRange, MessageSquareWarning, Lock, Bell, Send, Smartphone, Mail, Globe, Shield, Zap, ExternalLink, ChevronRight, Brain, ChevronDown, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api-client";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ConfirmDialog } from "@/components/confirm-dialog";
import type { LlmProvider, AgentConfig, KnowledgeGraph, DiscoveredField, SastRuleProfile, EmailTemplate, OidcProvider, OidcProviderCreate } from "@/lib/types";
import { useProjects } from "@/hooks/use-projects";
import { useCustomFields, useDiscoverCustomFields, useBulkUpsertCustomFields, useDeleteCustomField } from "@/hooks/use-custom-fields";
import { KnowledgeGraphEditor } from "@/components/knowledge-graph-editor";
import {
  useSSHKeys, useCreateSSHKey, useDeleteSSHKey,
  usePlatformCredentials, useCreatePlatformCredential, useDeletePlatformCredential, useTestPlatformCredential,
  useUsers, useCreateUser, useUpdateUser, useResetUserMfa, useDeleteUser,
  useFileExclusions, useCreateFileExclusion, useUpdateFileExclusion, useDeleteFileExclusion, useLoadDefaultExclusions,
  useAiSettings, useUpdateAiSettings,
  useLlmProviders, useCreateLlmProvider, useUpdateLlmProvider, useDeleteLlmProvider,
  useAgents, useCreateAgent, useUpdateAgent, useDeleteAgent,
  useAiTools,
  useKnowledgeGraphs, useKnowledgeGraph, useCreateKnowledgeGraph, useUpdateKnowledgeGraph, useDeleteKnowledgeGraph, useRegenerateKnowledgeGraph,
  useSmtpSettings, useUpdateSmtpSettings, useTestSmtp,
  useEmailTemplates, useUpdateEmailTemplate, usePreviewEmailTemplate,
  useAuthSettings, useUpdateAuthSettings,
  useOidcProviders, useOidcProvider, useCreateOidcProvider, useUpdateOidcProvider, useDeleteOidcProvider,
  useDiscoverOidc, useTestOidcProvider,
} from "@/hooks/use-settings";
import {
  useSastProfiles, useCreateSastProfile, useUpdateSastProfile, useDeleteSastProfile,
  useSastSettings, useUpdateSastSettings,
  useGlobalIgnoredRules, useAddGlobalIgnoredRule, useRemoveGlobalIgnoredRule,
} from "@/hooks/use-sast";
import { useFeedback, useUpdateFeedback, useDeleteFeedback } from "@/hooks/use-feedback";
import type { FeedbackItem } from "@/lib/types";
import { MfaSetupDialog } from "@/components/mfa-setup-dialog";
import AccessPolicySettings from "@/components/access-policy-settings";
import { LocalAgentEditModal } from "@/components/local-agent-edit-modal";
import { A2AAgentEditModal } from "@/components/a2a-agent-edit-modal";
import type { A2AAgentConfig } from "@/components/a2a-agent-edit-modal";

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

function OidcProviderDialog({ open, onOpenChange, editId }: { open: boolean; onOpenChange: (open: boolean) => void; editId: string | null }) {
  const { data: existing } = useOidcProvider(editId);
  const createProvider = useCreateOidcProvider();
  const updateProvider = useUpdateOidcProvider();
  const discoverOidc = useDiscoverOidc();
  const testProvider = useTestOidcProvider();

  const [step, setStep] = useState(0);
  const [providerType, setProviderType] = useState<string>("keycloak");
  const [form, setForm] = useState({
    name: "",
    client_id: "",
    client_secret: "",
    discovery_url: "",
    authorization_url: "",
    token_url: "",
    userinfo_url: "",
    jwks_url: "",
    scopes: "openid profile email",
    email_claim: "email",
    name_claim: "name",
    groups_claim: "groups",
    admin_groups: "",
    auto_provision: true,
    enabled: false,
    realm_url: "",
    tenant_id: "",
  });
  const [discoverError, setDiscoverError] = useState("");
  const [testResult, setTestResult] = useState<Record<string, boolean | string> | null>(null);

  useEffect(() => {
    if (editId && existing) {
      setProviderType(existing.provider_type);
      setForm({
        name: existing.name,
        client_id: existing.client_id,
        client_secret: "",
        discovery_url: existing.discovery_url ?? "",
        authorization_url: existing.authorization_url,
        token_url: existing.token_url,
        userinfo_url: existing.userinfo_url ?? "",
        jwks_url: existing.jwks_url,
        scopes: existing.scopes,
        email_claim: existing.claim_mapping?.email ?? "email",
        name_claim: existing.claim_mapping?.name ?? "name",
        groups_claim: existing.claim_mapping?.groups ?? "groups",
        admin_groups: (existing.claim_mapping?.admin_groups ?? []).join(", "),
        auto_provision: existing.auto_provision,
        enabled: existing.enabled,
        realm_url: "",
        tenant_id: "",
      });
      setStep(1);
    } else {
      setStep(0);
      setForm({
        name: "", client_id: "", client_secret: "", discovery_url: "", authorization_url: "",
        token_url: "", userinfo_url: "", jwks_url: "", scopes: "openid profile email",
        email_claim: "email", name_claim: "name", groups_claim: "groups", admin_groups: "",
        auto_provision: true, enabled: false, realm_url: "", tenant_id: "",
      });
      setProviderType("keycloak");
    }
    setDiscoverError("");
    setTestResult(null);
  }, [editId, existing, open]);

  async function handleDiscover() {
    setDiscoverError("");
    let url = form.discovery_url;
    if (!url && providerType === "keycloak" && form.realm_url) {
      url = `${form.realm_url.replace(/\/$/, "")}/.well-known/openid-configuration`;
    }
    if (!url && providerType === "azure_entra" && form.tenant_id) {
      url = `https://login.microsoftonline.com/${form.tenant_id}/v2.0/.well-known/openid-configuration`;
    }
    if (!url) { setDiscoverError("Provide a discovery URL"); return; }
    try {
      const result = await discoverOidc.mutateAsync({ id: editId ?? undefined, discovery_url: url });
      setForm(prev => ({
        ...prev,
        discovery_url: url,
        authorization_url: result.authorization_endpoint,
        token_url: result.token_endpoint,
        userinfo_url: result.userinfo_endpoint ?? "",
        jwks_url: result.jwks_uri,
      }));
    } catch (err: unknown) {
      setDiscoverError(err instanceof Error ? err.message : "Discovery failed");
    }
  }

  async function handleSave() {
    const data: OidcProviderCreate = {
      name: form.name,
      provider_type: providerType,
      client_id: form.client_id,
      client_secret: form.client_secret || undefined,
      discovery_url: form.discovery_url || undefined,
      authorization_url: form.authorization_url,
      token_url: form.token_url,
      userinfo_url: form.userinfo_url || undefined,
      jwks_url: form.jwks_url,
      scopes: form.scopes,
      claim_mapping: {
        email: form.email_claim,
        name: form.name_claim,
        groups: form.groups_claim,
        admin_groups: form.admin_groups ? form.admin_groups.split(",").map(s => s.trim()).filter(Boolean) : [],
      },
      auto_provision: form.auto_provision,
      enabled: form.enabled,
    };
    if (editId) {
      await updateProvider.mutateAsync({ id: editId, data });
    } else {
      await createProvider.mutateAsync(data);
    }
    onOpenChange(false);
  }

  const providerTypes = [
    { value: "keycloak", label: "Keycloak", desc: "Open-source IAM with realm-based multi-tenancy", icon: <Shield className="h-6 w-6" /> },
    { value: "azure_entra", label: "Azure Entra ID", desc: "Microsoft cloud identity (formerly Azure AD)", icon: <Globe className="h-6 w-6" /> },
    { value: "generic_oidc", label: "Generic OIDC", desc: "Any OpenID Connect compliant provider", icon: <Key className="h-6 w-6" /> },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editId ? "Edit Provider" : "Add Identity Provider"}</DialogTitle>
        </DialogHeader>

        {step === 0 && !editId && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Choose a provider type:</p>
            {providerTypes.map(pt => (
              <button
                key={pt.value}
                onClick={() => { setProviderType(pt.value); setStep(1); }}
                className={`flex w-full items-start gap-3 rounded-lg border p-4 text-left transition-colors hover:bg-accent ${providerType === pt.value ? "border-primary bg-accent" : ""}`}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted">{pt.icon}</div>
                <div>
                  <p className="text-sm font-medium">{pt.label}</p>
                  <p className="text-xs text-muted-foreground">{pt.desc}</p>
                </div>
              </button>
            ))}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Display Name</Label>
              <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="e.g. Corporate Keycloak" />
            </div>

            {providerType === "keycloak" && (
              <div className="space-y-2">
                <Label>Keycloak Realm URL</Label>
                <Input value={form.realm_url} onChange={e => setForm(p => ({ ...p, realm_url: e.target.value }))} placeholder="https://keycloak.example.com/realms/myrealm" />
                <p className="text-xs text-muted-foreground">Discovery URL will be derived from this.</p>
              </div>
            )}

            {providerType === "azure_entra" && (
              <div className="space-y-2">
                <Label>Tenant ID</Label>
                <Input value={form.tenant_id} onChange={e => setForm(p => ({ ...p, tenant_id: e.target.value }))} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
                <p className="text-xs text-muted-foreground">Discovery URL will be derived from this.</p>
              </div>
            )}

            <div className="space-y-2">
              <Label>Discovery URL</Label>
              <div className="flex gap-2">
                <Input value={form.discovery_url} onChange={e => setForm(p => ({ ...p, discovery_url: e.target.value }))} placeholder=".well-known/openid-configuration URL" className="flex-1" />
                <Button variant="outline" size="sm" onClick={handleDiscover} disabled={discoverOidc.isPending}>
                  {discoverOidc.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                  <span className="ml-1">Discover</span>
                </Button>
              </div>
              {discoverError && <p className="text-xs text-destructive">{discoverError}</p>}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Client ID</Label>
                <Input value={form.client_id} onChange={e => setForm(p => ({ ...p, client_id: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Client Secret</Label>
                <Input type="password" value={form.client_secret} onChange={e => setForm(p => ({ ...p, client_secret: e.target.value }))} placeholder={editId ? "(unchanged)" : ""} />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Authorization URL</Label>
              <Input value={form.authorization_url} onChange={e => setForm(p => ({ ...p, authorization_url: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>Token URL</Label>
              <Input value={form.token_url} onChange={e => setForm(p => ({ ...p, token_url: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>UserInfo URL</Label>
                <Input value={form.userinfo_url} onChange={e => setForm(p => ({ ...p, userinfo_url: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>JWKS URL</Label>
                <Input value={form.jwks_url} onChange={e => setForm(p => ({ ...p, jwks_url: e.target.value }))} />
              </div>
            </div>

            <div className="flex justify-between pt-2">
              {!editId && <Button variant="ghost" onClick={() => setStep(0)}>Back</Button>}
              {editId && <div />}
              <Button onClick={() => setStep(2)}>Next</Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm font-medium">Advanced Settings</p>

            <div className="space-y-2">
              <Label>Scopes</Label>
              <Input value={form.scopes} onChange={e => setForm(p => ({ ...p, scopes: e.target.value }))} />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-2">
                <Label>Email claim</Label>
                <Input value={form.email_claim} onChange={e => setForm(p => ({ ...p, email_claim: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Name claim</Label>
                <Input value={form.name_claim} onChange={e => setForm(p => ({ ...p, name_claim: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Groups claim</Label>
                <Input value={form.groups_claim} onChange={e => setForm(p => ({ ...p, groups_claim: e.target.value }))} />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Admin group names</Label>
              <Input value={form.admin_groups} onChange={e => setForm(p => ({ ...p, admin_groups: e.target.value }))} placeholder="admin, super-admin" />
              <p className="text-xs text-muted-foreground">Comma-separated group values that grant admin access.</p>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Auto-provision users</p>
                <p className="text-xs text-muted-foreground">Create accounts on first OIDC login</p>
              </div>
              <Switch checked={form.auto_provision} onCheckedChange={v => setForm(p => ({ ...p, auto_provision: v }))} />
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Enabled</p>
                <p className="text-xs text-muted-foreground">Show on the login page</p>
              </div>
              <Switch checked={form.enabled} onCheckedChange={v => setForm(p => ({ ...p, enabled: v }))} />
            </div>

            {editId && (
              <div className="pt-1">
                <Button variant="outline" size="sm" className="gap-1.5" onClick={() => testProvider.mutate(editId)} disabled={testProvider.isPending}>
                  {testProvider.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  Test Connection
                </Button>
                {testProvider.data && (
                  <div className="mt-2 space-y-1 text-xs">
                    {Object.entries(testProvider.data).filter(([k]) => !k.endsWith("_error")).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-1.5">
                        {v === true ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500" /> : <AlertCircle className="h-3.5 w-3.5 text-destructive" />}
                        <span className="capitalize">{k}</span>
                        {v !== true && <span className="text-destructive ml-1">({String(testProvider.data?.[`${k}_error`] ?? "failed")})</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-between pt-2">
              <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={handleSave} disabled={createProvider.isPending || updateProvider.isPending || !form.name || !form.client_id}>
                {(createProvider.isPending || updateProvider.isPending) ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {editId ? "Save Changes" : "Create Provider"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AuthSettingsSection() {
  const { data: authSettings } = useAuthSettings();
  const updateAuth = useUpdateAuthSettings();
  const { data: oidcProviders } = useOidcProviders();
  const deleteProvider = useDeleteOidcProvider();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  function typeLabel(t: string) {
    if (t === "keycloak") return "Keycloak";
    if (t === "azure_entra") return "Azure Entra ID";
    return "Generic OIDC";
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Multi-Factor Authentication Policy</CardTitle>
          <CardDescription>Configure MFA enforcement for local authentication users.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <p className="text-sm font-medium">Force MFA for all local users</p>
              <p className="text-xs text-muted-foreground">When enabled, users authenticating with local credentials will be required to set up MFA after their next login.</p>
            </div>
            <Switch
              checked={authSettings?.force_mfa_local_auth ?? false}
              onCheckedChange={(checked) => updateAuth.mutate({ force_mfa_local_auth: checked })}
              disabled={updateAuth.isPending}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Local Authentication</CardTitle>
          <CardDescription>Username and password login stored in the application database.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <p className="text-sm font-medium">Enable local login</p>
              <p className="text-xs text-muted-foreground">When disabled, only admin accounts can use local login as a fallback.</p>
            </div>
            <Switch
              checked={authSettings?.local_login_enabled ?? true}
              onCheckedChange={(checked) => updateAuth.mutate({ local_login_enabled: checked })}
              disabled={updateAuth.isPending}
            />
          </div>
          {authSettings && !authSettings.local_login_enabled && (
            <div className="mt-3 flex items-start gap-2 rounded-md bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>Local login is disabled. Only admin accounts can sign in with username/password. Make sure at least one OIDC provider is enabled.</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Identity Providers (OIDC)</CardTitle>
            <CardDescription>Configure external identity providers for single sign-on.</CardDescription>
          </div>
          <Button size="sm" className="gap-1.5" onClick={() => { setEditId(null); setDialogOpen(true); }}>
            <Plus className="h-4 w-4" /> Add Provider
          </Button>
        </CardHeader>
        <CardContent>
          {oidcProviders && oidcProviders.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {oidcProviders.map(p => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="text-muted-foreground">{typeLabel(p.provider_type)}</TableCell>
                    <TableCell>
                      <Badge variant={p.enabled ? "default" : "secondary"}>{p.enabled ? "Enabled" : "Disabled"}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => { setEditId(p.id); setDialogOpen(true); }}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(p.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <Globe className="mx-auto h-8 w-8 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">No identity providers configured.</p>
              <p className="text-xs text-muted-foreground">Add a Keycloak, Azure Entra ID, or generic OIDC provider to enable single sign-on.</p>
            </div>
          )}
        </CardContent>
      </Card>

      <OidcProviderDialog open={dialogOpen} onOpenChange={setDialogOpen} editId={editId} />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title="Delete Identity Provider"
        description="This will remove the provider and unlink any users provisioned through it. This cannot be undone."
        onConfirm={() => { if (deleteTarget) { deleteProvider.mutate(deleteTarget); setDeleteTarget(null); } }}
        variant="destructive"
      />
    </div>
  );
}

function NotificationsSettingsSection() {
  const { data: smtp } = useSmtpSettings();
  const updateSmtp = useUpdateSmtpSettings();
  const testSmtp = useTestSmtp();
  const { data: templates = [] } = useEmailTemplates();
  const updateTemplate = useUpdateEmailTemplate();
  const previewTemplate = usePreviewEmailTemplate();

  const [smtpForm, setSmtpForm] = useState<{
    host: string; port: string; username: string; password: string;
    from_email: string; from_name: string; use_tls: boolean; enabled: boolean;
  }>({ host: "", port: "587", username: "", password: "", from_email: "", from_name: "Contributr", use_tls: true, enabled: false });
  const [smtpDirty, setSmtpDirty] = useState(false);
  const [editTemplate, setEditTemplate] = useState<EmailTemplate | null>(null);
  const [tplSubject, setTplSubject] = useState("");
  const [tplHtml, setTplHtml] = useState("");
  const [tplText, setTplText] = useState("");
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);

  // Sync SMTP form when data loads
  const smtpLoaded = useRef(false);
  if (smtp && !smtpLoaded.current) {
    smtpLoaded.current = true;
    setSmtpForm({
      host: smtp.host, port: String(smtp.port), username: smtp.username, password: "",
      from_email: smtp.from_email, from_name: smtp.from_name, use_tls: smtp.use_tls, enabled: smtp.enabled,
    });
  }

  function handleSmtpField(field: string, value: string | boolean) {
    setSmtpForm((f) => ({ ...f, [field]: value }));
    setSmtpDirty(true);
  }

  async function handleSmtpSave() {
    const data: Record<string, unknown> = {};
    if (smtpForm.host !== (smtp?.host ?? "")) data.host = smtpForm.host;
    if ((parseInt(smtpForm.port) || 587) !== (smtp?.port ?? 587)) data.port = parseInt(smtpForm.port) || 587;
    if (smtpForm.username !== (smtp?.username ?? "")) data.username = smtpForm.username;
    if (smtpForm.from_email !== (smtp?.from_email ?? "")) data.from_email = smtpForm.from_email;
    if (smtpForm.from_name !== (smtp?.from_name ?? "Contributr")) data.from_name = smtpForm.from_name;
    if (smtpForm.use_tls !== (smtp?.use_tls ?? true)) data.use_tls = smtpForm.use_tls;
    if (smtpForm.enabled !== (smtp?.enabled ?? false)) data.enabled = smtpForm.enabled;
    if (smtpForm.password) data.password = smtpForm.password;
    if (Object.keys(data).length === 0) return;
    await updateSmtp.mutateAsync(data as Parameters<typeof updateSmtp.mutateAsync>[0]);
    setSmtpDirty(false);
    smtpLoaded.current = false;
  }

  function openTemplateEditor(tpl: EmailTemplate) {
    setEditTemplate(tpl);
    setTplSubject(tpl.subject);
    setTplHtml(tpl.body_html);
    setTplText(tpl.body_text);
    setPreviewHtml(null);
  }

  async function handleTemplateSave() {
    if (!editTemplate) return;
    await updateTemplate.mutateAsync({ slug: editTemplate.slug, data: { subject: tplSubject, body_html: tplHtml, body_text: tplText } });
    setEditTemplate(null);
  }

  async function handleTemplatePreview() {
    if (!editTemplate) return;
    const result = await previewTemplate.mutateAsync({ slug: editTemplate.slug });
    setPreviewHtml(result.body_html);
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>SMTP Configuration</CardTitle>
          <CardDescription>Configure outbound email for notifications, OTP codes, and alerts.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>SMTP Host</Label>
              <Input value={smtpForm.host} onChange={(e) => handleSmtpField("host", e.target.value)} placeholder="smtp.example.com" />
            </div>
            <div className="space-y-2">
              <Label>Port</Label>
              <Input value={smtpForm.port} onChange={(e) => handleSmtpField("port", e.target.value)} placeholder="587" />
            </div>
            <div className="space-y-2">
              <Label>Username</Label>
              <Input value={smtpForm.username} onChange={(e) => handleSmtpField("username", e.target.value)} placeholder="user@example.com" />
            </div>
            <div className="space-y-2">
              <Label>Password</Label>
              <Input type="password" value={smtpForm.password} onChange={(e) => handleSmtpField("password", e.target.value)} placeholder={smtp?.has_password ? "••••••••" : "Enter password"} />
            </div>
            <div className="space-y-2">
              <Label>From Email</Label>
              <Input value={smtpForm.from_email} onChange={(e) => handleSmtpField("from_email", e.target.value)} placeholder="noreply@example.com" />
            </div>
            <div className="space-y-2">
              <Label>From Name</Label>
              <Input value={smtpForm.from_name} onChange={(e) => handleSmtpField("from_name", e.target.value)} placeholder="Contributr" />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={smtpForm.use_tls} onCheckedChange={(v) => handleSmtpField("use_tls", v)} />
              Use TLS
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={smtpForm.enabled} onCheckedChange={(v) => handleSmtpField("enabled", v)} />
              Enabled
            </label>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSmtpSave} disabled={!smtpDirty && !updateSmtp.isPending}>
              {updateSmtp.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save"}
            </Button>
            <Button
              variant="outline"
              onClick={() => testSmtp.mutate({})}
              disabled={testSmtp.isPending || !smtp?.enabled}
            >
              {testSmtp.isPending
                ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Sending...</>
                : testSmtp.isSuccess
                  ? <><CheckCircle2 className="mr-2 h-4 w-4 text-green-500" /> Sent</>
                  : <><Send className="mr-2 h-4 w-4" /> Test Connection</>}
            </Button>
          </div>
          {testSmtp.isError && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {testSmtp.error instanceof Error ? testSmtp.error.message : "Test failed"}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Email Templates</CardTitle>
          <CardDescription>Manage Jinja2 email templates used for notifications and OTP codes.</CardDescription>
        </CardHeader>
        <CardContent>
          {templates.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No email templates configured.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Slug</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {templates.map((tpl) => (
                  <TableRow key={tpl.slug}>
                    <TableCell><code className="text-xs">{tpl.slug}</code></TableCell>
                    <TableCell>{tpl.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">{tpl.subject}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openTemplateEditor(tpl)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!editTemplate} onOpenChange={(v) => { if (!v) setEditTemplate(null); }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Template: {editTemplate?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Subject</Label>
              <Input value={tplSubject} onChange={(e) => setTplSubject(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>HTML Body</Label>
              <Textarea value={tplHtml} onChange={(e) => setTplHtml(e.target.value)} rows={10} className="font-mono text-xs" />
            </div>
            <div className="space-y-2">
              <Label>Plain Text Body</Label>
              <Textarea value={tplText} onChange={(e) => setTplText(e.target.value)} rows={4} className="font-mono text-xs" />
            </div>
            {editTemplate?.variables && Object.keys(editTemplate.variables).length > 0 && (
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Available variables</Label>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(editTemplate.variables).map(([k, v]) => (
                    <Badge key={k} variant="outline" className="text-xs font-mono">
                      {"{{ " + k + " }}"} <span className="ml-1 font-sans text-muted-foreground">— {v.description}</span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={handleTemplateSave} disabled={updateTemplate.isPending}>
                {updateTemplate.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save"}
              </Button>
              <Button variant="outline" onClick={handleTemplatePreview} disabled={previewTemplate.isPending}>
                {previewTemplate.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Previewing...</> : <><Eye className="mr-2 h-4 w-4" /> Preview</>}
              </Button>
            </div>
            {previewHtml && (
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Preview (with sample data)</Label>
                <div className="rounded-lg border bg-white p-4" dangerouslySetInnerHTML={{ __html: previewHtml }} />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UserSecuritySection() {
  const { user, refresh } = useAuth();
  const [mfaSetupOpen, setMfaSetupOpen] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableError, setDisableError] = useState("");
  const [disabling, setDisabling] = useState(false);
  const [regenPassword, setRegenPassword] = useState("");
  const [regenError, setRegenError] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleDisable() {
    setDisableError("");
    setDisabling(true);
    try {
      await api.mfaDisable({ password: disablePassword });
      setDisablePassword("");
      await refresh();
    } catch (err: unknown) {
      setDisableError(err instanceof Error ? err.message : "Failed to disable MFA");
    } finally {
      setDisabling(false);
    }
  }

  async function handleRegenerate() {
    setRegenError("");
    setRegenerating(true);
    try {
      const res = await api.mfaRegenerateRecoveryCodes({ password: regenPassword });
      setRecoveryCodes(res.recovery_codes);
      setRegenPassword("");
    } catch (err: unknown) {
      setRegenError(err instanceof Error ? err.message : "Failed to regenerate codes");
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Two-Factor Authentication</CardTitle>
          <CardDescription>Add an extra layer of security to your account.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!user?.mfa_enabled ? (
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                  <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium">MFA is not enabled</p>
                  <p className="text-xs text-muted-foreground">Enable MFA to add an extra layer of security</p>
                </div>
              </div>
              <Button size="sm" onClick={() => setMfaSetupOpen(true)}>Set up MFA</Button>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <p className="text-sm font-medium">Enrolled Methods</p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div className="flex items-center gap-3">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full ${(user.mfa_methods ?? []).includes("totp") ? "bg-green-100 dark:bg-green-900/30" : "bg-muted"}`}>
                        <Smartphone className={`h-4 w-4 ${(user.mfa_methods ?? []).includes("totp") ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`} />
                      </div>
                      <div>
                        <p className="text-sm font-medium">Authenticator App</p>
                        <p className="text-xs text-muted-foreground">Use an app like Google Authenticator or Authy</p>
                      </div>
                    </div>
                    {(user.mfa_methods ?? []).includes("totp") ? (
                      <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Enrolled</Badge>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => setMfaSetupOpen(true)}>Enroll</Button>
                    )}
                  </div>
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div className="flex items-center gap-3">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full ${(user.mfa_methods ?? []).includes("email") ? "bg-green-100 dark:bg-green-900/30" : "bg-muted"}`}>
                        <Mail className={`h-4 w-4 ${(user.mfa_methods ?? []).includes("email") ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`} />
                      </div>
                      <div>
                        <p className="text-sm font-medium">Email OTP</p>
                        <p className="text-xs text-muted-foreground">Receive a one-time code via email</p>
                      </div>
                    </div>
                    {(user.mfa_methods ?? []).includes("email") ? (
                      <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Enrolled</Badge>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => setMfaSetupOpen(true)}>Enroll</Button>
                    )}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Disable MFA</p>
                <p className="text-xs text-muted-foreground">Enter your password to remove all MFA methods from your account.</p>
                {disableError && <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{disableError}</div>}
                <div className="flex gap-2">
                  <Input type="password" placeholder="Your password" value={disablePassword} onChange={(e) => setDisablePassword(e.target.value)} className="max-w-xs" />
                  <Button variant="destructive" size="sm" onClick={handleDisable} disabled={disabling || !disablePassword}>
                    {disabling ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Disable All
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Recovery Codes</p>
                <p className="text-xs text-muted-foreground">Generate new recovery codes. This will invalidate any existing codes.</p>
                {regenError && <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{regenError}</div>}
                <div className="flex gap-2">
                  <Input type="password" placeholder="Your password" value={regenPassword} onChange={(e) => setRegenPassword(e.target.value)} className="max-w-xs" />
                  <Button variant="outline" size="sm" onClick={handleRegenerate} disabled={regenerating || !regenPassword}>
                    {regenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Regenerate
                  </Button>
                </div>
                {recoveryCodes && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2 rounded-lg bg-muted/50 p-4">
                      {recoveryCodes.map((c, i) => (
                        <code key={i} className="text-center font-mono text-sm">{c}</code>
                      ))}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => { navigator.clipboard.writeText(recoveryCodes.join("\n")); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                    >
                      {copied ? <><Check className="mr-1.5 h-3.5 w-3.5" /> Copied</> : <><Copy className="mr-1.5 h-3.5 w-3.5" /> Copy</>}
                    </Button>
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <MfaSetupDialog
        open={mfaSetupOpen}
        onOpenChange={setMfaSetupOpen}
        dismissible
        onComplete={async (at, rt) => {
          if (at && rt) {
            localStorage.setItem("access_token", at);
            localStorage.setItem("refresh_token", rt);
          }
          await refresh();
          setMfaSetupOpen(false);
        }}
      />
    </div>
  );
}

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
  const updateUser = useUpdateUser();
  const resetUserMfa = useResetUserMfa();
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

  const CATEGORY_LABELS: Record<string, string> = {
    contribution_analytics: "Contribution Analytics",
    delivery_analytics: "Delivery Analytics",
    code_access: "Code Access",
    sast_analytics: "SAST Analytics",
    sql_query: "SQL Query",
  };

  const CATEGORY_COLORS: Record<string, string> = {
    contribution_analytics: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    delivery_analytics: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
    code_access: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
    sast_analytics: "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200",
    sql_query: "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-200",
  };


  const toolCategoryIndex = useMemo(() => {
    const idx: Record<string, string> = {};
    for (const t of aiTools) idx[t.slug] = t.category;
    return idx;
  }, [aiTools]);

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
  const [userForm, setUserForm] = useState({ email: "", username: "", password: "", full_name: "", is_admin: false, send_invite: true, temporary_password: true });
  const [editUserOpen, setEditUserOpen] = useState(false);
  const [editUserId, setEditUserId] = useState<string | null>(null);
  const [editUserForm, setEditUserForm] = useState({ email: "", username: "", full_name: "", is_admin: false, is_active: true, password: "" });
  const [mfaEnrollUserId, setMfaEnrollUserId] = useState<string | null>(null);
  const [resetMfaUserId, setResetMfaUserId] = useState<string | null>(null);

  const [newPattern, setNewPattern] = useState("");
  const [newDesc, setNewDesc] = useState("");

  // LLM Provider form
  const [providerOpen, setProviderOpen] = useState(false);
  const [editProvider, setEditProvider] = useState<LlmProvider | null>(null);
  const [providerForm, setProviderForm] = useState({ name: "", provider_type: "openai", model: "", model_type: "chat" as "chat" | "embedding", api_key: "", base_url: "", temperature: "0.1", context_window: "", is_default: false });
  const [showProviderKey, setShowProviderKey] = useState(false);

  // Agent form
  const [agentOpen, setAgentOpen] = useState(false);
  const [editAgentSlug, setEditAgentSlug] = useState<string | null>(null);
  const [a2aOpen, setA2aOpen] = useState(false);
  const [editA2aAgent, setEditA2aAgent] = useState<A2AAgentConfig | null>(null);

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

  // Feedback state
  const [fbSourceFilter, setFbSourceFilter] = useState<string>("all");
  const [fbStatusFilter, setFbStatusFilter] = useState<string>("all");
  const [fbAgentFilter, setFbAgentFilter] = useState<string>("all");
  const { data: feedbackData, refetch: refetchFeedback, isFetching: isFetchingFeedback } = useFeedback({
    source: fbSourceFilter !== "all" ? fbSourceFilter : undefined,
    status: fbStatusFilter !== "all" ? fbStatusFilter : undefined,
    agent_slug: fbAgentFilter !== "all" ? fbAgentFilter : undefined,
    limit: 100,
  });
  const updateFeedback = useUpdateFeedback();
  const deleteFeedback = useDeleteFeedback();
  const [fbDetailItem, setFbDetailItem] = useState<FeedbackItem | null>(null);
  const [fbAdminNotes, setFbAdminNotes] = useState("");
  const [fbDetailStatus, setFbDetailStatus] = useState<string>("new");
  const [deleteFeedbackId, setDeleteFeedbackId] = useState<string | null>(null);

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
    setUserForm({ email: "", username: "", password: "", full_name: "", is_admin: false, send_invite: true, temporary_password: true });
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
        model_type: provider.model_type || "chat",
        api_key: "",
        base_url: provider.base_url || "",
        temperature: String(provider.temperature),
        context_window: provider.context_window ? String(provider.context_window) : "",
        is_default: provider.is_default,
      });
    } else {
      setEditProvider(null);
      setProviderForm({ name: "", provider_type: "openai", model: "", model_type: "chat", api_key: "", base_url: "", temperature: "0.1", context_window: "", is_default: false });
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
      model_type: providerForm.model_type,
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
    } else {
      setEditAgentSlug(null);
    }
    setAgentOpen(true);
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

      <Tabs defaultValue="ssh-keys" orientation="vertical" className="gap-6 items-start">
        <TabsList variant="line" className="w-48 shrink-0 sticky top-4 gap-0.5">
          <TabsTrigger value="ssh-keys" className="gap-2"><Key className="h-4 w-4" /> SSH Keys</TabsTrigger>
          <TabsTrigger value="platform-tokens" className="gap-2"><ShieldCheck className="h-4 w-4" /> Platform Tokens</TabsTrigger>
          {user?.is_admin && <TabsTrigger value="users" className="gap-2"><Users className="h-4 w-4" /> Users</TabsTrigger>}
          {user?.is_admin && <TabsTrigger value="ai" className="gap-2"><Bot className="h-4 w-4" /> AI</TabsTrigger>}
          {user?.is_admin && <TabsTrigger value="auth-settings" className="gap-2"><Lock className="h-4 w-4" /> Auth</TabsTrigger>}
          {user?.is_admin && <TabsTrigger value="notifications" className="gap-2"><Bell className="h-4 w-4" /> Notifications</TabsTrigger>}
          <TabsTrigger value="security" className="gap-2"><ShieldCheck className="h-4 w-4" /> Security</TabsTrigger>
          <TabsTrigger value="file-exclusions" className="gap-2"><FileX2 className="h-4 w-4" /> File Exclusions</TabsTrigger>
          <TabsTrigger value="custom-fields" className="gap-2"><ListFilter className="h-4 w-4" /> Custom Fields</TabsTrigger>
          <TabsTrigger value="delivery" className="gap-2"><CalendarRange className="h-4 w-4" /> Delivery</TabsTrigger>
          <TabsTrigger value="sast" className="gap-2"><ShieldAlert className="h-4 w-4" /> SAST</TabsTrigger>
          <TabsTrigger value="feedback" className="gap-2"><MessageSquareWarning className="h-4 w-4" /> Feedback</TabsTrigger>
          <TabsTrigger value="backup" className="gap-2"><Database className="h-4 w-4" /> Backup</TabsTrigger>
          {user?.is_admin && <TabsTrigger value="access-policies" className="gap-2"><Shield className="h-4 w-4" /> Access Policies</TabsTrigger>}
        </TabsList>

        <TabsContent value="ssh-keys" className="min-w-0 space-y-4">
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

        <TabsContent value="platform-tokens" className="min-w-0 space-y-4">
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
          <TabsContent value="users" className="min-w-0 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Manage user accounts, roles, MFA enrollment, and access.</p>
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
                    <div className="flex items-center gap-2">
                      <input type="checkbox" id="temporary_password" checked={userForm.temporary_password} onChange={(e) => setUserForm((f) => ({ ...f, temporary_password: e.target.checked }))} />
                      <Label htmlFor="temporary_password">Set as temporary password (force change on login)</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input type="checkbox" id="send_invite" checked={userForm.send_invite} onChange={(e) => setUserForm((f) => ({ ...f, send_invite: e.target.checked }))} />
                      <Label htmlFor="send_invite">Send invite email</Label>
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
                    <TableHead>Provider</TableHead>
                    <TableHead>MFA</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-32" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id} className={!u.is_active ? "opacity-50" : undefined}>
                      <TableCell className="font-medium">{u.username}</TableCell>
                      <TableCell className="text-muted-foreground">{u.email}</TableCell>
                      <TableCell>{u.full_name || "-"}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">
                          {u.auth_provider === "oidc" ? "OIDC" : "Local"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {(u.mfa_methods ?? []).length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {(u.mfa_methods ?? []).map((m) => (
                              <Badge key={m} variant="default" className="gap-1 text-[10px]">
                                <ShieldCheck className="h-3 w-3" /> {m === "totp" ? "TOTP" : "Email"}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <Badge variant="secondary" className="text-[10px]">Off</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={u.is_admin ? "default" : "secondary"}>
                          {u.is_admin ? "Admin" : "Viewer"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {u.is_active ? (
                          <Badge variant="outline" className="border-green-500/40 text-green-600 text-[10px]">Active</Badge>
                        ) : (
                          <Badge variant="outline" className="border-red-500/40 text-red-500 text-[10px]">Disabled</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={() => {
                                    setEditUserId(u.id);
                                    setEditUserForm({
                                      email: u.email,
                                      username: u.username,
                                      full_name: u.full_name || "",
                                      is_admin: u.is_admin,
                                      is_active: u.is_active,
                                      password: "",
                                    });
                                    setEditUserOpen(true);
                                  }}
                                >
                                  <Pencil className="h-3 w-3" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Edit user</TooltipContent>
                            </Tooltip>
                          </TooltipProvider>

                          {u.auth_provider === "local" && (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  {u.mfa_enabled ? (
                                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setResetMfaUserId(u.id)}>
                                      <ShieldAlert className="h-3 w-3 text-amber-500" />
                                    </Button>
                                  ) : (
                                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setMfaEnrollUserId(u.id)}>
                                      <ShieldCheck className="h-3 w-3 text-muted-foreground" />
                                    </Button>
                                  )}
                                </TooltipTrigger>
                                <TooltipContent>{u.mfa_enabled ? "Reset MFA" : "Enroll MFA"}</TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}

                          {u.id !== user?.id && (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteUserId(u.id)}>
                                    <Trash2 className="h-3 w-3 text-destructive" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>Delete user</TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>

            {/* Edit User Dialog */}
            <Dialog open={editUserOpen} onOpenChange={(open) => { setEditUserOpen(open); if (!open) setEditUserId(null); }}>
              <DialogContent>
                <DialogHeader><DialogTitle>Edit User</DialogTitle></DialogHeader>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!editUserId) return;
                    const data: Record<string, unknown> = {};
                    const original = users.find((u) => u.id === editUserId);
                    if (editUserForm.email !== original?.email) data.email = editUserForm.email;
                    if (editUserForm.username !== original?.username) data.username = editUserForm.username;
                    if (editUserForm.full_name !== (original?.full_name || "")) data.full_name = editUserForm.full_name || null;
                    if (editUserForm.is_admin !== original?.is_admin) data.is_admin = editUserForm.is_admin;
                    if (editUserForm.is_active !== original?.is_active) data.is_active = editUserForm.is_active;
                    if (editUserForm.password) data.password = editUserForm.password;
                    await updateUser.mutateAsync({ id: editUserId, data });
                    setEditUserOpen(false);
                    setEditUserId(null);
                  }}
                  className="space-y-4"
                >
                  <div className="space-y-2">
                    <Label>Full name</Label>
                    <Input value={editUserForm.full_name} onChange={(e) => setEditUserForm((f) => ({ ...f, full_name: e.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input type="email" value={editUserForm.email} onChange={(e) => setEditUserForm((f) => ({ ...f, email: e.target.value }))} required />
                  </div>
                  <div className="space-y-2">
                    <Label>Username</Label>
                    <Input value={editUserForm.username} onChange={(e) => setEditUserForm((f) => ({ ...f, username: e.target.value }))} required />
                  </div>
                  <div className="space-y-2">
                    <Label>New password</Label>
                    <Input type="password" value={editUserForm.password} onChange={(e) => setEditUserForm((f) => ({ ...f, password: e.target.value }))} placeholder="Leave blank to keep current" />
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Switch checked={editUserForm.is_admin} onCheckedChange={(v) => setEditUserForm((f) => ({ ...f, is_admin: v }))} id="edit_is_admin" />
                      <Label htmlFor="edit_is_admin">Admin</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch checked={editUserForm.is_active} onCheckedChange={(v) => setEditUserForm((f) => ({ ...f, is_active: v }))} id="edit_is_active" />
                      <Label htmlFor="edit_is_active">Active</Label>
                    </div>
                  </div>
                  <Button type="submit" className="w-full" disabled={updateUser.isPending}>
                    {updateUser.isPending ? "Saving..." : "Save Changes"}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>

            {/* MFA Enroll -- for own account, open the shared MfaSetupDialog directly; for others, show info dialog */}
            {mfaEnrollUserId && mfaEnrollUserId === user?.id && (
              <MfaSetupDialog
                open={true}
                onOpenChange={() => setMfaEnrollUserId(null)}
                dismissible={true}
                onComplete={(accessToken, refreshToken) => {
                  if (typeof window !== "undefined") {
                    localStorage.setItem("access_token", accessToken);
                    localStorage.setItem("refresh_token", refreshToken);
                  }
                  setMfaEnrollUserId(null);
                }}
              />
            )}
            <Dialog open={!!mfaEnrollUserId && mfaEnrollUserId !== user?.id} onOpenChange={(open) => { if (!open) setMfaEnrollUserId(null); }}>
              <DialogContent className="max-w-md">
                <DialogHeader><DialogTitle>Enroll MFA</DialogTitle></DialogHeader>
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    MFA can only be enrolled by the user themselves. To prompt this user to set up MFA:
                  </p>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                    <li>Enable <strong>Force MFA for all local users</strong> in the Auth settings tab</li>
                    <li>The user will be required to set up MFA on their next login</li>
                  </ul>
                  <Button className="w-full" onClick={() => setMfaEnrollUserId(null)}>Got it</Button>
                </div>
              </DialogContent>
            </Dialog>

            {/* Reset MFA Confirm Dialog */}
            <ConfirmDialog
              open={!!resetMfaUserId}
              onOpenChange={(open) => { if (!open) setResetMfaUserId(null); }}
              title="Reset MFA"
              description="This will disable MFA for this user and remove their authenticator and recovery codes. They will need to enroll again if MFA is required."
              confirmLabel="Reset MFA"
              onConfirm={() => { if (resetMfaUserId) { resetUserMfa.mutate(resetMfaUserId); setResetMfaUserId(null); } }}
              variant="destructive"
            />
          </TabsContent>
        )}
        {user?.is_admin && (
          <TabsContent value="ai" className="min-w-0 space-y-6">
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
                      <TableHead>Purpose</TableHead>
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
                        <TableCell><Badge variant={p.model_type === "embedding" ? "secondary" : "outline"} className="text-[10px] uppercase">{p.model_type || "chat"}</Badge></TableCell>
                        <TableCell className="max-w-[140px] truncate font-mono text-sm">{p.model}</TableCell>
                        <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">{p.base_url || "-"}</TableCell>
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
                        <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">No LLM providers configured. Add one to get started.</TableCell>
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
                  <div className="grid gap-4 sm:grid-cols-3">
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
                      <Label>Purpose</Label>
                      <Select value={providerForm.model_type} onValueChange={(v) => setProviderForm((f) => ({ ...f, model_type: v as "chat" | "embedding" }))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="chat">Chat (LLM)</SelectItem>
                          <SelectItem value="embedding">Embedding</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">Chat for agents, embedding for memory</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Model</Label>
                      <Input value={providerForm.model} onChange={(e) => setProviderForm((f) => ({ ...f, model: e.target.value }))} placeholder={providerForm.model_type === "embedding" ? "text-embedding-3-small" : "gpt-4o-mini, claude-3-sonnet..."} required />
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

            {/* Memory Section */}
            {aiSettingsData && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base"><Brain className="h-4 w-4" /> Memory</CardTitle>
                  <CardDescription>Configure long-term memory, background extraction, and context management.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Master toggle */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Enable long-term memory</p>
                      <p className="text-xs text-muted-foreground">Vector-backed memory with save/search tools and background extraction</p>
                    </div>
                    <Switch
                      checked={aiSettingsData.memory_enabled}
                      onCheckedChange={(checked) => updateAiSettings.mutate({ memory_enabled: checked })}
                    />
                  </div>

                  {aiSettingsData.memory_enabled && (
                    <>
                      {/* Embedding provider */}
                      <div className="space-y-2">
                        <Label>Embedding Provider</Label>
                        <Select
                          value={aiSettingsData.memory_embedding_provider_id ?? "none"}
                          onValueChange={(v) => updateAiSettings.mutate({ memory_embedding_provider_id: v === "none" ? null : v })}
                        >
                          <SelectTrigger><SelectValue placeholder="Select embedding provider" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Not configured</SelectItem>
                            {llmProviders.filter((p) => p.model_type === "embedding").map((p) => (
                              <SelectItem key={p.id} value={p.id}>{p.name} — {p.model}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">Embedding model used to index and search long-term memories</p>
                      </div>

                      {/* Background Extraction */}
                      <details className="group rounded-md border px-3 py-2">
                        <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium [&::-webkit-details-marker]:hidden">
                          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                          Background Extraction
                        </summary>
                        <div className="mt-3 space-y-4 pb-1">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm">Auto-extract memories from conversations</p>
                              <p className="text-xs text-muted-foreground">Uses LangMem to identify facts, preferences, and patterns</p>
                            </div>
                            <Switch
                              checked={aiSettingsData.extraction_enabled}
                              onCheckedChange={(checked) => updateAiSettings.mutate({ extraction_enabled: checked })}
                            />
                          </div>

                          {aiSettingsData.extraction_enabled && (
                            <>
                              <div className="space-y-2">
                                <Label>Extraction Model</Label>
                                <Select
                                  value={aiSettingsData.extraction_provider_id ?? "none"}
                                  onValueChange={(v) => updateAiSettings.mutate({ extraction_provider_id: v === "none" ? null : v })}
                                >
                                  <SelectTrigger><SelectValue placeholder="Select extraction model" /></SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="none">Not configured</SelectItem>
                                    {llmProviders.filter((p) => p.model_type === "chat").map((p) => (
                                      <SelectItem key={p.id} value={p.id}>{p.name} — {p.model}</SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <p className="text-xs text-muted-foreground">Chat model used by LangMem to extract and organise memories</p>
                              </div>

                              <div className="space-y-2">
                                <Label className="text-xs font-medium text-muted-foreground">Extraction Behavior</Label>
                                <div className="space-y-2">
                                  <label className="flex items-center gap-2 text-sm">
                                    <input
                                      type="checkbox"
                                      checked={aiSettingsData.extraction_enable_inserts}
                                      onChange={(e) => updateAiSettings.mutate({ extraction_enable_inserts: e.target.checked })}
                                    />
                                    Allow creating new memories
                                  </label>
                                  <label className="flex items-center gap-2 text-sm">
                                    <input
                                      type="checkbox"
                                      checked={aiSettingsData.extraction_enable_updates}
                                      onChange={(e) => updateAiSettings.mutate({ extraction_enable_updates: e.target.checked })}
                                    />
                                    Allow updating existing memories
                                  </label>
                                  <label className="flex items-center gap-2 text-sm">
                                    <input
                                      type="checkbox"
                                      checked={aiSettingsData.extraction_enable_deletes}
                                      onChange={(e) => updateAiSettings.mutate({ extraction_enable_deletes: e.target.checked })}
                                    />
                                    Allow deleting contradicted memories
                                  </label>
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      </details>

                      {/* Context Management (Advanced) */}
                      <details className="group rounded-md border px-3 py-2">
                        <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium [&::-webkit-details-marker]:hidden">
                          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                          Advanced: Context Management
                        </summary>
                        <div className="mt-3 space-y-5 pb-1">
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <Label>Cleanup Threshold</Label>
                              <span className="text-xs tabular-nums text-muted-foreground">{Math.round(aiSettingsData.cleanup_threshold_ratio * 100)}%</span>
                            </div>
                            <Slider
                              min={30} max={90} step={5}
                              value={[Math.round(aiSettingsData.cleanup_threshold_ratio * 100)]}
                              onValueCommit={([v]) => updateAiSettings.mutate({ cleanup_threshold_ratio: v / 100 })}
                            />
                            <p className="text-xs text-muted-foreground">Evict old messages when checkpoint exceeds this % of context window</p>
                          </div>

                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <Label>Summary Size</Label>
                              <span className="text-xs tabular-nums text-muted-foreground">{Math.round(aiSettingsData.summary_token_ratio * 100)}%</span>
                            </div>
                            <Slider
                              min={1} max={10} step={1}
                              value={[Math.round(aiSettingsData.summary_token_ratio * 100)]}
                              onValueCommit={([v]) => updateAiSettings.mutate({ summary_token_ratio: v / 100 })}
                            />
                            <p className="text-xs text-muted-foreground">Rolling summary size as a fraction of context window</p>
                          </div>
                        </div>
                      </details>

                      {/* Info callout */}
                      <div className="flex gap-2 rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300">
                        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>Memory requires an embedding provider. Add one in LLM Providers above with type set to &quot;Embedding&quot;. Changes to embedding provider or the memory toggle require a server restart to take effect.</span>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

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
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => setA2aOpen(true)}>
                    <Globe className="mr-2 h-4 w-4" /> Add A2A Agent
                  </Button>
                  <Button size="sm" onClick={() => openAgentDialog()}>
                    <Plus className="mr-2 h-4 w-4" /> Add Agent
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Slug</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>LLM Provider</TableHead>
                      <TableHead>Tools / Members</TableHead>
                      <TableHead>Enabled</TableHead>
                      <TableHead className="w-28" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {agents.map((a) => {
                      const provider = llmProviders.find((p) => p.id === a.llm_provider_id);
                      const isSupervisor = a.agent_type === "supervisor";
                      return (
                        <TableRow key={a.id}>
                          <TableCell className="font-medium">
                            <div className="flex items-center gap-2">
                              {a.name}
                              {a.is_builtin && <Badge variant="secondary" className="text-[10px]">built-in</Badge>}
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-sm text-muted-foreground">{a.slug}</TableCell>
                          <TableCell>
                            {isSupervisor
                              ? <Badge className="text-[10px] bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-200 hover:bg-violet-100">Supervisor</Badge>
                              : <Badge variant="outline" className="text-[10px]">Standard</Badge>
                            }
                          </TableCell>
                          <TableCell className="text-sm">{provider?.name || <span className="text-muted-foreground">None</span>}</TableCell>
                          <TableCell>
                            {isSupervisor
                              ? <Badge variant="outline" className="text-[10px]">{(a.member_agent_ids || []).length} agents</Badge>
                              : (() => {
                                  const cats: Record<string, number> = {};
                                  for (const s of a.tool_slugs) {
                                    const cat = toolCategoryIndex[s];
                                    if (cat) cats[cat] = (cats[cat] || 0) + 1;
                                  }
                                  const entries = Object.entries(cats).sort(([, a], [, b]) => b - a);
                                  return entries.length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                      {entries.map(([cat, count]) => (
                                        <Badge key={cat} className={`text-[10px] ${CATEGORY_COLORS[cat] || ""}`}>
                                          {(CATEGORY_LABELS[cat] || cat).replace(/ Analytics| Access/, "")} {count}
                                        </Badge>
                                      ))}
                                    </div>
                                  ) : (
                                    <Badge variant="outline" className="text-[10px]">{a.tool_slugs.length || "All"} tools</Badge>
                                  );
                                })()
                            }
                          </TableCell>
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
                        <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">No agents configured.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* Local Agent Edit Modal */}
            <LocalAgentEditModal
              open={agentOpen}
              onOpenChange={setAgentOpen}
              agent={editAgentSlug ? agents.find((a) => a.slug === editAgentSlug) ?? null : null}
              llmProviders={llmProviders}
            />

            {/* A2A Agent Edit Modal */}
            <A2AAgentEditModal
              open={a2aOpen}
              onOpenChange={(v) => { setA2aOpen(v); if (!v) setEditA2aAgent(null); }}
              agent={editA2aAgent}
              onSave={async () => { /* TODO: wire to backend A2A CRUD once available */ }}
            />
          </TabsContent>
        )}
        <TabsContent value="file-exclusions" className="min-w-0 space-y-4">
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

        <TabsContent value="custom-fields" className="min-w-0 space-y-4">
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

        <TabsContent value="delivery" className="min-w-0 space-y-4">
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

        <TabsContent value="sast" className="min-w-0 space-y-4">
          <SastSettingsSection />
        </TabsContent>

        {user?.is_admin && (
          <TabsContent value="auth-settings" className="min-w-0 space-y-4">
            <AuthSettingsSection />
          </TabsContent>
        )}

        {user?.is_admin && (
          <TabsContent value="notifications" className="min-w-0 space-y-4">
            <NotificationsSettingsSection />
          </TabsContent>
        )}

        <TabsContent value="security" className="min-w-0 space-y-4">
          <UserSecuritySection />
        </TabsContent>

        <TabsContent value="backup" className="min-w-0 space-y-4">
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

        {user?.is_admin && (
          <TabsContent value="access-policies" className="min-w-0 space-y-4">
            <AccessPolicySettings />
          </TabsContent>
        )}

        <TabsContent value="feedback" className="min-w-0 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Feedback & Capability Gaps</CardTitle>
              <CardDescription>Agent-reported gaps and human feedback on AI responses. Review, annotate, and track resolution.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-3 mb-4">
                <div className="flex items-center gap-2">
                  <Label className="text-xs whitespace-nowrap">Source</Label>
                  <Select value={fbSourceFilter} onValueChange={setFbSourceFilter}>
                    <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="agent">Agent</SelectItem>
                      <SelectItem value="human">Human</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <Label className="text-xs whitespace-nowrap">Status</Label>
                  <Select value={fbStatusFilter} onValueChange={setFbStatusFilter}>
                    <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="new">New</SelectItem>
                      <SelectItem value="reviewed">Reviewed</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <Label className="text-xs whitespace-nowrap">Agent</Label>
                  <Select value={fbAgentFilter} onValueChange={setFbAgentFilter}>
                    <SelectTrigger className="w-[160px] h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Agents</SelectItem>
                      {agents.map((a) => (
                        <SelectItem key={a.slug} value={a.slug}>{a.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1.5"
                  onClick={() => refetchFeedback()}
                  disabled={isFetchingFeedback}
                >
                  <RefreshCw className={`h-3 w-3 ${isFetchingFeedback ? "animate-spin" : ""}`} />
                  Refresh
                </Button>
              </div>

              {!feedbackData?.items?.length ? (
                <p className="text-sm text-muted-foreground py-8 text-center">No feedback yet.</p>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[140px]">Date</TableHead>
                        <TableHead className="w-[80px]">Source</TableHead>
                        <TableHead className="w-[120px]">Category</TableHead>
                        <TableHead>Content</TableHead>
                        <TableHead className="w-[120px]">Agent</TableHead>
                        <TableHead className="w-[90px]">Status</TableHead>
                        <TableHead className="w-[80px]">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {feedbackData.items.map((item) => (
                        <TableRow
                          key={item.id}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => {
                            setFbDetailItem(item);
                            setFbAdminNotes(item.admin_notes || "");
                            setFbDetailStatus(item.status);
                          }}
                        >
                          <TableCell className="text-xs text-muted-foreground">
                            {new Date(item.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                          </TableCell>
                          <TableCell>
                            <Badge variant={item.source === "agent" ? "secondary" : "outline"} className="text-xs">
                              {item.source === "agent" ? "Agent" : "Human"}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">{item.category || "—"}</TableCell>
                          <TableCell className="text-xs max-w-[300px] truncate">{item.content}</TableCell>
                          <TableCell className="text-xs">{item.agent_slug || "—"}</TableCell>
                          <TableCell>
                            <Badge variant={
                              item.status === "new" ? "default" :
                              item.status === "reviewed" ? "secondary" : "outline"
                            } className="text-xs">
                              {item.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={(e) => { e.stopPropagation(); setDeleteFeedbackId(item.id); }}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {feedbackData && feedbackData.total > 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                  Showing {feedbackData.items.length} of {feedbackData.total} item{feedbackData.total !== 1 ? "s" : ""}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Feedback detail dialog */}
      <Dialog open={!!fbDetailItem} onOpenChange={(v) => { if (!v) setFbDetailItem(null); }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Feedback Detail</DialogTitle>
          </DialogHeader>
          {fbDetailItem && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Badge variant={fbDetailItem.source === "agent" ? "secondary" : "outline"}>
                  {fbDetailItem.source === "agent" ? "Agent" : "Human"}
                </Badge>
                {fbDetailItem.category && <Badge variant="outline">{fbDetailItem.category}</Badge>}
                <Badge variant={
                  fbDetailItem.status === "new" ? "default" :
                  fbDetailItem.status === "reviewed" ? "secondary" : "outline"
                }>
                  {fbDetailItem.status}
                </Badge>
              </div>

              <div>
                <Label className="text-xs text-muted-foreground">Content</Label>
                <p className="text-sm mt-1 whitespace-pre-wrap">{fbDetailItem.content}</p>
              </div>

              {fbDetailItem.user_query && (
                <div>
                  <Label className="text-xs text-muted-foreground">User Query</Label>
                  <p className="text-sm mt-1 whitespace-pre-wrap bg-muted p-2 rounded text-muted-foreground">{fbDetailItem.user_query}</p>
                </div>
              )}

              {fbDetailItem.agent_slug && (
                <div>
                  <Label className="text-xs text-muted-foreground">Agent</Label>
                  <p className="text-sm mt-1">{fbDetailItem.agent_slug}</p>
                </div>
              )}

              <div className="text-xs text-muted-foreground">
                Created: {new Date(fbDetailItem.created_at).toLocaleString()}
                {fbDetailItem.updated_at !== fbDetailItem.created_at && (
                  <> &middot; Updated: {new Date(fbDetailItem.updated_at).toLocaleString()}</>
                )}
              </div>

              <div className="border-t pt-4 space-y-3">
                <div className="space-y-1">
                  <Label className="text-xs">Status</Label>
                  <Select value={fbDetailStatus} onValueChange={setFbDetailStatus}>
                    <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="new">New</SelectItem>
                      <SelectItem value="reviewed">Reviewed</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Admin Notes</Label>
                  <Textarea
                    value={fbAdminNotes}
                    onChange={(e) => setFbAdminNotes(e.target.value)}
                    rows={3}
                    placeholder="Add notes about this feedback..."
                    className="text-sm"
                  />
                </div>
                <Button
                  size="sm"
                  className="w-full"
                  disabled={updateFeedback.isPending}
                  onClick={async () => {
                    await updateFeedback.mutateAsync({
                      id: fbDetailItem.id,
                      status: fbDetailStatus,
                      admin_notes: fbAdminNotes,
                    });
                    setFbDetailItem(null);
                  }}
                >
                  {updateFeedback.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Save Changes
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteFeedbackId}
        onOpenChange={(v) => !v && setDeleteFeedbackId(null)}
        title="Delete Feedback"
        description="This will permanently remove this feedback item. This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => { if (deleteFeedbackId) { deleteFeedback.mutate(deleteFeedbackId); setDeleteFeedbackId(null); } }}
      />

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
