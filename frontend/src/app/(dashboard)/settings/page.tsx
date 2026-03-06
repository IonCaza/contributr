"use client";

import { useEffect, useState, useRef } from "react";
import { Key, Users, Plus, Trash2, Copy, Check, Download, Upload, Database, Loader2, CheckCircle2, AlertCircle, Bot, Eye, EyeOff, FileX2, ShieldCheck, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api-client";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { SSHKey, User, AiSettings, FileExclusionPattern, PlatformCredential } from "@/lib/types";

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

export default function SettingsPage() {
  const { user } = useAuth();
  const [sshKeys, setSSHKeys] = useState<SSHKey[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [keyName, setKeyName] = useState("");
  const [keyType, setKeyType] = useState<"ed25519" | "rsa">("ed25519");
  const [rsaBits, setRsaBits] = useState<string>("4096");
  const [keyOpen, setKeyOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [userForm, setUserForm] = useState({ email: "", username: "", password: "", full_name: "", is_admin: false });
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<Record<string, { submitted: number; imported: number }> | null>(null);
  const [backupError, setBackupError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [exclusions, setExclusions] = useState<FileExclusionPattern[]>([]);
  const [newPattern, setNewPattern] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [loadingDefaults, setLoadingDefaults] = useState(false);

  const [credentials, setCredentials] = useState<PlatformCredential[]>([]);
  const [credOpen, setCredOpen] = useState(false);
  const [credForm, setCredForm] = useState({ name: "", platform: "azure", token: "", base_url: "" });
  const [credTesting, setCredTesting] = useState<string | null>(null);
  const [credTestResult, setCredTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null);

  const [aiSettings, setAiSettings] = useState<AiSettings | null>(null);
  const [aiForm, setAiForm] = useState({ model: "", api_key: "", base_url: "", temperature: "0.1", max_iterations: "10" });
  const [aiSaving, setAiSaving] = useState(false);
  const [aiSaved, setAiSaved] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    api.listSSHKeys().then(setSSHKeys);
    api.listPlatformCredentials().then(setCredentials).catch(() => {});
    api.listFileExclusions().then(setExclusions).catch(() => {});
    if (user?.is_admin) {
      api.listUsers().then(setUsers);
      api.getAiSettings().then((s) => {
        setAiSettings(s);
        setAiForm({
          model: s.model,
          api_key: "",
          base_url: s.base_url || "",
          temperature: String(s.temperature),
          max_iterations: String(s.max_iterations),
        });
      }).catch(() => {});
    }
  }, [user]);

  async function handleCreateKey(e: React.FormEvent) {
    e.preventDefault();
    const key = await api.createSSHKey({
      name: keyName,
      key_type: keyType,
      ...(keyType === "rsa" ? { rsa_bits: parseInt(rsaBits) } : {}),
    });
    setSSHKeys((prev) => [key, ...prev]);
    setKeyName("");
    setKeyType("ed25519");
    setRsaBits("4096");
    setKeyOpen(false);
  }

  async function handleDeleteKey(id: string) {
    await api.deleteSSHKey(id);
    setSSHKeys((prev) => prev.filter((k) => k.id !== id));
  }

  async function handleCreateCredential(e: React.FormEvent) {
    e.preventDefault();
    const cred = await api.createPlatformCredential({
      name: credForm.name,
      platform: credForm.platform,
      token: credForm.token,
      base_url: credForm.base_url || undefined,
    });
    setCredentials((prev) => [cred, ...prev]);
    setCredForm({ name: "", platform: "azure", token: "", base_url: "" });
    setCredOpen(false);
  }

  async function handleDeleteCredential(id: string) {
    await api.deletePlatformCredential(id);
    setCredentials((prev) => prev.filter((c) => c.id !== id));
  }

  async function handleTestCredential(id: string) {
    setCredTesting(id);
    setCredTestResult(null);
    try {
      const result = await api.testPlatformCredential(id);
      setCredTestResult({ id, ...result });
    } catch {
      setCredTestResult({ id, success: false, message: "Request failed" });
    } finally {
      setCredTesting(null);
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    const u = await api.createUser(userForm);
    setUsers((prev) => [...prev, u]);
    setUserForm({ email: "", username: "", password: "", full_name: "", is_admin: false });
    setUserOpen(false);
  }

  async function handleDeleteUser(id: string) {
    await api.deleteUser(id);
    setUsers((prev) => prev.filter((u) => u.id !== id));
  }

  async function handleSaveAi(e: React.FormEvent) {
    e.preventDefault();
    setAiSaving(true);
    setAiError(null);
    setAiSaved(false);
    try {
      const payload: Record<string, unknown> = {
        model: aiForm.model,
        temperature: parseFloat(aiForm.temperature) || 0.1,
        max_iterations: parseInt(aiForm.max_iterations) || 10,
        base_url: aiForm.base_url || "",
      };
      if (aiForm.api_key) payload.api_key = aiForm.api_key;
      const updated = await api.updateAiSettings(payload as Parameters<typeof api.updateAiSettings>[0]);
      setAiSettings(updated);
      setAiForm((f) => ({ ...f, api_key: "" }));
      setAiSaved(true);
      setTimeout(() => setAiSaved(false), 3000);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setAiSaving(false);
    }
  }

  async function handleToggleAi(checked?: boolean) {
    if (!aiSettings) return;
    const newValue = checked !== undefined ? checked : !aiSettings.enabled;
    try {
      const updated = await api.updateAiSettings({ enabled: newValue });
      setAiSettings(updated);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Failed to toggle");
    }
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
          {user?.is_admin && <TabsTrigger value="ai" className="gap-2"><Bot className="h-4 w-4" /> AI Agent</TabsTrigger>}
          <TabsTrigger value="file-exclusions" className="gap-2"><FileX2 className="h-4 w-4" /> File Exclusions</TabsTrigger>
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
                  <Button type="submit" className="w-full">Generate</Button>
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
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDeleteKey(k.id)}>
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
                  <Button type="submit" className="w-full">Save Token</Button>
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
                            <Button variant="ghost" size="icon" className="h-7 w-7" disabled={credTesting === c.id} onClick={() => handleTestCredential(c.id)}>
                              {credTesting === c.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
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
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDeleteCredential(c.id)}>
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
                    <Button type="submit" className="w-full">Create User</Button>
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
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDeleteUser(u.id)}>
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
          <TabsContent value="ai" className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Configure the AI agent that powers the conversational assistant. Requires an API key from your LLM provider.
            </p>

            {aiSettings && (
              <Card>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <Bot className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium">Enable AI Assistant</p>
                        <Badge variant={aiSettings.enabled && aiSettings.has_api_key ? "default" : "secondary"} className="text-[10px]">
                          {aiSettings.enabled && aiSettings.has_api_key ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {aiSettings.has_api_key
                          ? "Show the AI assistant to all users in the sidebar."
                          : "Configure an API key below before enabling."}
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={aiSettings.enabled}
                    onCheckedChange={handleToggleAi}
                    disabled={!aiSettings.has_api_key}
                  />
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Model Configuration</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSaveAi} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Model</Label>
                      <Input
                        value={aiForm.model}
                        onChange={(e) => setAiForm((f) => ({ ...f, model: e.target.value }))}
                        placeholder="gpt-4o-mini, claude-3-sonnet, ollama/llama3..."
                        required
                      />
                      <p className="text-xs text-muted-foreground">
                        LiteLLM model string. Supports OpenAI, Anthropic, Ollama, Azure, Bedrock, etc.
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label>API Key</Label>
                      <div className="relative">
                        <Input
                          type={showApiKey ? "text" : "password"}
                          value={aiForm.api_key}
                          onChange={(e) => setAiForm((f) => ({ ...f, api_key: e.target.value }))}
                          placeholder={aiSettings?.has_api_key ? "••••••• (key is set, enter new to replace)" : "sk-..."}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                          onClick={() => setShowApiKey(!showApiKey)}
                        >
                          {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground">Encrypted at rest. Leave blank to keep existing key.</p>
                    </div>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="space-y-2">
                      <Label>Base URL (optional)</Label>
                      <Input
                        value={aiForm.base_url}
                        onChange={(e) => setAiForm((f) => ({ ...f, base_url: e.target.value }))}
                        placeholder="https://api.openai.com/v1"
                      />
                      <p className="text-xs text-muted-foreground">For self-hosted or proxy endpoints.</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Temperature</Label>
                      <Input
                        type="number"
                        step="0.05"
                        min="0"
                        max="2"
                        value={aiForm.temperature}
                        onChange={(e) => setAiForm((f) => ({ ...f, temperature: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Max Iterations</Label>
                      <Input
                        type="number"
                        min="1"
                        max="25"
                        value={aiForm.max_iterations}
                        onChange={(e) => setAiForm((f) => ({ ...f, max_iterations: e.target.value }))}
                      />
                      <p className="text-xs text-muted-foreground">Max tool-calling loops per request.</p>
                    </div>
                  </div>

                  {aiError && (
                    <div className="flex items-center gap-2 text-sm text-destructive">
                      <AlertCircle className="h-4 w-4" />
                      {aiError}
                    </div>
                  )}

                  <div className="flex items-center gap-3">
                    <Button type="submit" disabled={aiSaving}>
                      {aiSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save Configuration"}
                    </Button>
                    {aiSaved && (
                      <span className="flex items-center gap-1 text-sm text-emerald-500">
                        <CheckCircle2 className="h-4 w-4" /> Saved
                      </span>
                    )}
                  </div>
                </form>
              </CardContent>
            </Card>
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
              disabled={loadingDefaults}
              onClick={async () => {
                setLoadingDefaults(true);
                try {
                  const res = await api.loadDefaultExclusions();
                  if (res.added > 0) setExclusions(await api.listFileExclusions());
                } catch { /* ignore */ }
                setLoadingDefaults(false);
              }}
            >
              {loadingDefaults ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
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
                    await api.createFileExclusion({ pattern: newPattern.trim(), description: newDesc.trim() || undefined });
                    setExclusions(await api.listFileExclusions());
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
                <Button type="submit" size="sm" disabled={!newPattern.trim()}>
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
                          onCheckedChange={async (checked) => {
                            await api.updateFileExclusion(ex.id, { enabled: checked });
                            setExclusions(await api.listFileExclusions());
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
                          onClick={async () => {
                            await api.deleteFileExclusion(ex.id);
                            setExclusions(await api.listFileExclusions());
                          }}
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
    </div>
  );
}
