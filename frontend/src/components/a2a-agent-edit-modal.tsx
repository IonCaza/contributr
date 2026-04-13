"use client";

import { useState } from "react";
import { Loader2, Globe, ShieldCheck, Zap, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

interface A2AAgentFormState {
  name: string;
  slug: string;
  description: string;
  url: string;
  auth_type: "none" | "bearer" | "api_key" | "oauth2";
  auth_token: string;
  timeout_seconds: string;
  enabled: boolean;
}

const DEFAULT_FORM: A2AAgentFormState = {
  name: "",
  slug: "",
  description: "",
  url: "",
  auth_type: "none",
  auth_token: "",
  timeout_seconds: "30",
  enabled: true,
};

export interface A2AAgentConfig {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  url: string;
  auth_type: "none" | "bearer" | "api_key" | "oauth2";
  timeout_seconds: number;
  enabled: boolean;
  agent_card: A2AAgentCard | null;
}

export interface A2AAgentCard {
  name: string;
  description: string;
  skills: { id: string; name: string; description: string }[];
  url: string;
  version: string;
  provider?: { organization: string };
}

interface A2AAgentEditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent: A2AAgentConfig | null;
  onSave: (data: Omit<A2AAgentFormState, "auth_token"> & { auth_token?: string }) => Promise<void>;
}

export function A2AAgentEditModal({ open, onOpenChange, agent, onSave }: A2AAgentEditModalProps) {
  const isEdit = !!agent;
  const [form, setForm] = useState<A2AAgentFormState>(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredCard, setDiscoveredCard] = useState<A2AAgentCard | null>(null);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  function handleOpenChange(next: boolean) {
    if (next) {
      if (agent) {
        setForm({
          name: agent.name,
          slug: agent.slug,
          description: agent.description || "",
          url: agent.url,
          auth_type: agent.auth_type,
          auth_token: "",
          timeout_seconds: String(agent.timeout_seconds),
          enabled: agent.enabled,
        });
        setDiscoveredCard(agent.agent_card);
      } else {
        setForm({ ...DEFAULT_FORM });
        setDiscoveredCard(null);
      }
      setDiscoverError(null);
    }
    onOpenChange(next);
  }

  async function handleDiscover() {
    if (!form.url) return;
    setDiscovering(true);
    setDiscoverError(null);
    setDiscoveredCard(null);
    try {
      const wellKnown = form.url.replace(/\/+$/, "") + "/.well-known/agent.json";
      const resp = await fetch(wellKnown);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      const card: A2AAgentCard = await resp.json();
      setDiscoveredCard(card);
      if (!form.name && card.name) setForm((f) => ({ ...f, name: card.name }));
      if (!form.description && card.description) setForm((f) => ({ ...f, description: card.description }));
      if (!form.slug && card.name) {
        const autoSlug = card.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
        setForm((f) => ({ ...f, slug: autoSlug }));
      }
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : "Failed to discover agent");
    } finally {
      setDiscovering(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        name: form.name,
        slug: form.slug,
        description: form.description,
        url: form.url,
        auth_type: form.auth_type,
        ...(form.auth_token ? { auth_token: form.auth_token } : {}),
        timeout_seconds: form.timeout_seconds,
        enabled: form.enabled,
      });
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  }

  const card = discoveredCard;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            {isEdit ? "Edit A2A Agent" : "Register A2A Agent"}
          </DialogTitle>
          <DialogDescription>
            Connect to a remote agent using the Agent-to-Agent (A2A) protocol.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSave} className="space-y-4">
          {/* URL + Discover */}
          <div className="space-y-2">
            <Label>Agent URL <span className="text-destructive">*</span></Label>
            <div className="flex gap-2">
              <Input
                value={form.url}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                placeholder="https://remote-agent.example.com"
                className="flex-1"
                required
              />
              <Button type="button" variant="outline" size="sm" onClick={handleDiscover} disabled={discovering || !form.url}>
                {discovering ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
                Discover
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              The base URL of the remote A2A agent. Click Discover to fetch its agent card from <code className="rounded bg-muted px-1">/.well-known/agent.json</code>.
            </p>
            {discoverError && (
              <p className="text-xs text-destructive">{discoverError}</p>
            )}
          </div>

          {/* Discovered Agent Card */}
          {card && (
            <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{card.name}</p>
                <div className="flex items-center gap-2">
                  {card.version && <Badge variant="outline" className="text-[10px]">v{card.version}</Badge>}
                  {card.provider?.organization && <Badge variant="secondary" className="text-[10px]">{card.provider.organization}</Badge>}
                </div>
              </div>
              {card.description && (
                <p className="text-xs text-muted-foreground">{card.description}</p>
              )}
              {card.skills && card.skills.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium flex items-center gap-1"><Zap className="h-3 w-3" /> Skills</p>
                  <div className="flex flex-wrap gap-1">
                    {card.skills.map((s) => (
                      <Badge key={s.id} variant="outline" className="text-[10px]">{s.name}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Name + Slug */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Display Name <span className="text-destructive">*</span></Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Remote Analyst" required />
            </div>
            <div className="space-y-2">
              <Label>Slug</Label>
              <Input value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} placeholder="remote-analyst" disabled={isEdit} required />
              <p className="text-xs text-muted-foreground">Unique identifier. Cannot be changed after creation.</p>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label>Description</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="What does this remote agent do?"
              rows={3}
            />
          </div>

          {/* Auth */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2"><ShieldCheck className="h-3.5 w-3.5" /> Authentication</Label>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Select value={form.auth_type} onValueChange={(v) => setForm((f) => ({ ...f, auth_type: v as A2AAgentFormState["auth_type"] }))}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No Authentication</SelectItem>
                    <SelectItem value="bearer">Bearer Token</SelectItem>
                    <SelectItem value="api_key">API Key</SelectItem>
                    <SelectItem value="oauth2">OAuth 2.0</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {form.auth_type !== "none" && (
                <div className="space-y-2">
                  <Input
                    type="password"
                    value={form.auth_token}
                    onChange={(e) => setForm((f) => ({ ...f, auth_token: e.target.value }))}
                    placeholder={isEdit ? "••••••••  (leave blank to keep)" : "Enter token or key"}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Timeout */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Request Timeout (seconds)</Label>
              <Input
                type="number"
                min="5"
                max="300"
                value={form.timeout_seconds}
                onChange={(e) => setForm((f) => ({ ...f, timeout_seconds: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground">How long to wait for a response from the remote agent.</p>
            </div>
          </div>

          {/* Enabled */}
          <div className="flex items-center gap-2">
            <Switch checked={form.enabled} onCheckedChange={(checked) => setForm((f) => ({ ...f, enabled: checked }))} />
            <Label>Enabled</Label>
          </div>

          <Button type="submit" className="w-full" disabled={!form.url || !form.name || saving}>
            {saving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : isEdit ? "Save A2A Agent" : "Register A2A Agent"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
