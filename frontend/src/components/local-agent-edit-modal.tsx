"use client";

import { useState, useMemo } from "react";
import { Loader2, Users, Wrench, Search, ChevronRight, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useCreateAgent, useUpdateAgent, useAiTools, useKnowledgeGraphs, useAgents } from "@/hooks/use-settings";
import type { AgentConfig, LlmProvider } from "@/lib/types";

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

interface AgentFormState {
  slug: string;
  name: string;
  description: string;
  agent_type: "standard" | "supervisor";
  llm_provider_id: string;
  system_prompt: string;
  max_iterations: string;
  summary_token_limit: string;
  enabled: boolean;
  tool_slugs: string[];
  knowledge_graph_ids: string[];
  member_agent_ids: string[];
}

const DEFAULT_FORM: AgentFormState = {
  slug: "",
  name: "",
  description: "",
  agent_type: "standard",
  llm_provider_id: "",
  system_prompt: "",
  max_iterations: "10",
  summary_token_limit: "",
  enabled: true,
  tool_slugs: [],
  knowledge_graph_ids: [],
  member_agent_ids: [],
};

function formFromAgent(agent: AgentConfig): AgentFormState {
  return {
    slug: agent.slug,
    name: agent.name,
    description: agent.description || "",
    agent_type: agent.agent_type || "standard",
    llm_provider_id: agent.llm_provider_id || "",
    system_prompt: agent.system_prompt,
    max_iterations: String(agent.max_iterations),
    summary_token_limit: agent.summary_token_limit ? String(agent.summary_token_limit) : "",
    enabled: agent.enabled,
    tool_slugs: [...agent.tool_slugs],
    knowledge_graph_ids: [...(agent.knowledge_graph_ids || [])],
    member_agent_ids: [...(agent.member_agent_ids || [])],
  };
}

interface LocalAgentEditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent: AgentConfig | null;
  llmProviders: LlmProvider[];
}

export function LocalAgentEditModal({ open, onOpenChange, agent, llmProviders }: LocalAgentEditModalProps) {
  const isEdit = !!agent;
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent();
  const { data: agents = [] } = useAgents();
  const { data: aiTools = [] } = useAiTools();
  const { data: knowledgeGraphs = [] } = useKnowledgeGraphs();

  const [form, setForm] = useState<AgentFormState>(DEFAULT_FORM);
  const [toolSearch, setToolSearch] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());

  const groupedTools = useMemo(() => {
    const q = toolSearch.toLowerCase().trim();
    const filtered = q
      ? aiTools.filter((t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q))
      : aiTools;
    const groups: Record<string, typeof filtered> = {};
    for (const tool of filtered) {
      const cat = tool.category || "other";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(tool);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [aiTools, toolSearch]);

  function handleOpenChange(next: boolean) {
    if (next) {
      setForm(agent ? formFromAgent(agent) : { ...DEFAULT_FORM });
      setToolSearch("");
      setCollapsedCategories(new Set());
    }
    onOpenChange(next);
  }

  function toggleToolSlug(slug: string) {
    setForm((f) => ({
      ...f,
      tool_slugs: f.tool_slugs.includes(slug)
        ? f.tool_slugs.filter((s) => s !== slug)
        : [...f.tool_slugs, slug],
    }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const data = {
      name: form.name,
      description: form.description || undefined,
      agent_type: form.agent_type,
      llm_provider_id: form.llm_provider_id || undefined,
      system_prompt: form.system_prompt,
      max_iterations: parseInt(form.max_iterations) || 10,
      summary_token_limit: form.summary_token_limit ? parseInt(form.summary_token_limit) : null,
      enabled: form.enabled,
      tool_slugs: form.tool_slugs,
      knowledge_graph_ids: form.knowledge_graph_ids,
      member_agent_ids: form.agent_type === "supervisor" ? form.member_agent_ids : [],
    };

    if (isEdit) {
      await updateAgent.mutateAsync({ slug: agent!.slug, data });
    } else {
      await createAgent.mutateAsync({ slug: form.slug, ...data });
    }
    onOpenChange(false);
  }

  const chatProviders = llmProviders.filter((p) => (p.model_type || "chat") === "chat");
  const isSaving = createAgent.isPending || updateAgent.isPending;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Agent" : "Create Agent"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSave} className="space-y-4">
          {/* Name + Slug */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Contribution Analyst" required />
            </div>
            <div className="space-y-2">
              <Label>Slug</Label>
              <Input value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} placeholder="contribution-analyst" disabled={isEdit} required />
              <p className="text-xs text-muted-foreground">Unique identifier. Cannot be changed after creation.</p>
            </div>
          </div>

          {/* Description + Agent Type */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Description</Label>
              <Input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="What does this agent do?" />
            </div>
            <div className="space-y-2">
              <Label>Agent Type</Label>
              <Select value={form.agent_type} onValueChange={(v) => setForm((f) => ({ ...f, agent_type: v as "standard" | "supervisor" }))}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="standard">Standard Agent</SelectItem>
                  <SelectItem value="supervisor">Supervisor Agent</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {form.agent_type === "supervisor"
                  ? "Orchestrates other agents by delegating sub-tasks."
                  : "A regular agent with direct tool access."}
              </p>
            </div>
          </div>

          {/* LLM Provider + Iterations + Summary Token */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="min-w-0 space-y-2">
              <Label>LLM Provider <span className="text-destructive">*</span></Label>
              <Select value={form.llm_provider_id} onValueChange={(v) => setForm((f) => ({ ...f, llm_provider_id: v }))}>
                <SelectTrigger className={`w-full overflow-hidden [&>span:first-child]:truncate ${!form.llm_provider_id ? "border-destructive/50" : ""}`}><SelectValue placeholder="Select a provider..." /></SelectTrigger>
                <SelectContent>
                  {chatProviders.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} ({p.model})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!form.llm_provider_id && <p className="text-xs text-destructive">An LLM provider is required.</p>}
            </div>
            <div className="space-y-2">
              <Label>Max Iterations</Label>
              <Input type="number" min="1" max="999" value={form.max_iterations} onChange={(e) => setForm((f) => ({ ...f, max_iterations: e.target.value }))} />
              <p className="text-xs text-muted-foreground">Max tool-calling loops.</p>
            </div>
            <div className="space-y-2">
              <Label>Summary Token Limit</Label>
              <Input type="number" min="100" value={form.summary_token_limit} onChange={(e) => setForm((f) => ({ ...f, summary_token_limit: e.target.value }))} placeholder="Auto" />
              <p className="text-xs text-muted-foreground">~4% of context window.</p>
            </div>
          </div>

          {/* System Prompt */}
          <div className="space-y-2">
            <Label>System Prompt</Label>
            <Textarea
              value={form.system_prompt}
              onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
              placeholder="You are an AI assistant that..."
              rows={10}
              className="font-mono text-sm"
            />
          </div>

          {/* Supervisor: Member Agents */}
          {form.agent_type === "supervisor" && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><Users className="h-3.5 w-3.5" /> Member Agents</Label>
              <p className="text-xs text-muted-foreground">Select which agents this supervisor can delegate to. Only non-supervisor agents are shown.</p>
              <div className="grid gap-2 sm:grid-cols-2 mt-2">
                {agents.filter((a) => a.agent_type !== "supervisor" && a.slug !== form.slug).map((a) => (
                  <label key={a.id} className="flex items-start gap-2 rounded-md border p-2 cursor-pointer hover:bg-muted/50">
                    <input
                      type="checkbox"
                      checked={form.member_agent_ids.includes(a.id)}
                      onChange={() => {
                        setForm((f) => ({
                          ...f,
                          member_agent_ids: f.member_agent_ids.includes(a.id)
                            ? f.member_agent_ids.filter((id) => id !== a.id)
                            : [...f.member_agent_ids, a.id],
                        }));
                      }}
                      className="mt-0.5"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-tight">{a.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{a.description || a.slug} &middot; {a.tool_slugs.length} tools</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Tools */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2"><Wrench className="h-3.5 w-3.5" /> {form.agent_type === "supervisor" ? "Direct Tools" : "Assigned Tools"}</Label>
            <p className="text-xs text-muted-foreground">
              {form.agent_type === "supervisor"
                ? "Tools this supervisor can invoke directly (in addition to delegating to member agents). If none are selected, the supervisor has access to all tools."
                : "Select which tools this agent can use. If none are selected, the agent will have access to all tools."}
            </p>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search tools by name or description…"
                value={toolSearch}
                onChange={(e) => setToolSearch(e.target.value)}
                className="pl-9 h-9"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{form.tool_slugs.length} of {aiTools.length} tools selected</span>
              <div className="flex gap-2">
                <button type="button" className="hover:underline" onClick={() => setForm((f) => ({ ...f, tool_slugs: aiTools.map((t) => t.slug) }))}>Select all</button>
                <span>&middot;</span>
                <button type="button" className="hover:underline" onClick={() => setForm((f) => ({ ...f, tool_slugs: [] }))}>Clear</button>
              </div>
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto rounded-md border p-2">
              {groupedTools.map(([category, tools]) => {
                const isCollapsed = collapsedCategories.has(category);
                const selectedInGroup = tools.filter((t) => form.tool_slugs.includes(t.slug)).length;
                const allSelected = selectedInGroup === tools.length;
                const categorySlugs = tools.map((t) => t.slug);
                return (
                  <div key={category}>
                    <div className="flex items-center gap-2 sticky top-0 bg-background z-10 py-1">
                      <button
                        type="button"
                        className="flex items-center gap-1 text-sm font-medium hover:text-foreground transition-colors"
                        onClick={() => setCollapsedCategories((prev) => {
                          const next = new Set(prev);
                          isCollapsed ? next.delete(category) : next.add(category);
                          return next;
                        })}
                      >
                        <ChevronRight className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? "" : "rotate-90"}`} />
                        <Badge className={`text-[10px] font-medium ${CATEGORY_COLORS[category] || "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"}`}>
                          {CATEGORY_LABELS[category] || category}
                        </Badge>
                      </button>
                      <span className="text-[10px] text-muted-foreground">{selectedInGroup}/{tools.length}</span>
                      <button
                        type="button"
                        className="text-[10px] text-muted-foreground hover:underline ml-auto"
                        onClick={() => {
                          setForm((f) => ({
                            ...f,
                            tool_slugs: allSelected
                              ? f.tool_slugs.filter((s) => !categorySlugs.includes(s))
                              : [...new Set([...f.tool_slugs, ...categorySlugs])],
                          }));
                        }}
                      >
                        {allSelected ? "deselect all" : "select all"}
                      </button>
                    </div>
                    {!isCollapsed && (
                      <div className="grid gap-1.5 sm:grid-cols-2 pl-5 mt-1">
                        {tools.map((t) => (
                          <label key={t.slug} className="flex items-start gap-2 rounded-md border p-2 cursor-pointer hover:bg-muted/50">
                            <input
                              type="checkbox"
                              checked={form.tool_slugs.includes(t.slug)}
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
                    )}
                  </div>
                );
              })}
              {groupedTools.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">No tools match &ldquo;{toolSearch}&rdquo;</p>
              )}
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
                      checked={form.knowledge_graph_ids.includes(kg.id)}
                      onChange={() => {
                        setForm((f) => ({
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

          {/* Enabled */}
          <div className="flex items-center gap-2">
            <Switch checked={form.enabled} onCheckedChange={(checked) => setForm((f) => ({ ...f, enabled: checked }))} />
            <Label>Enabled</Label>
          </div>

          <Button type="submit" className="w-full" disabled={!form.llm_provider_id || isSaving}>
            {isSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save Agent"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
