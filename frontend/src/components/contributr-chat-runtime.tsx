"use client";

import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  useLocalRuntime,
  AssistantRuntimeProvider,
  unstable_useRemoteThreadListRuntime,
  useAuiState,
  type ChatModelAdapter,
  type unstable_RemoteThreadListAdapter,
} from "@assistant-ui/react";
import { ExportedMessageRepository } from "@assistant-ui/react";
import type { ThreadHistoryAdapter } from "@assistant-ui/core";
import { api } from "@/lib/api-client";
import type { AgentActivityRecord } from "@/lib/types";

/* ------------------------------------------------------------------ */
/*  Child-agent activity context (consumed by AgentActivityPanel)      */
/* ------------------------------------------------------------------ */

export interface ChildAgent {
  slug: string;
  content: string;
  done: boolean;
}

export interface ActivityGroup {
  triggerMessageId: string;
  triggerContent: string;
  agents: { runId: string; slug: string; content: string; done: boolean }[];
}

interface ChildAgentContextValue {
  /** Live agents streaming now (keyed by run_id). */
  liveAgents: Map<string, ChildAgent>;
  /** Historical activities loaded from the API on thread switch. */
  historicalActivities: ActivityGroup[];
  /** Whether the activity panel should be visible. */
  activityVisible: boolean;
  /** Show or hide the panel. */
  setActivityVisible: (v: boolean) => void;
  /** Clear live state (e.g. after streaming finishes or user dismisses). */
  clearLive: () => void;
  /** Reset all activity state (live + historical + visibility). */
  resetActivity: () => void;
  /** The user message text that triggered the current live run. */
  livePrompt: string;
}

const ChildAgentContext = createContext<ChildAgentContextValue>({
  liveAgents: new Map(),
  historicalActivities: [],
  activityVisible: false,
  setActivityVisible: () => {},
  clearLive: () => {},
  resetActivity: () => {},
  livePrompt: "",
});

export function useChildAgentActivity() {
  return useContext(ChildAgentContext);
}

export type AgentEventCallback = (
  event: string,
  data: Record<string, string>,
) => void;

/* ------------------------------------------------------------------ */
/*  Chat model adapter (SSE -> assistant-ui)                           */
/* ------------------------------------------------------------------ */

function makeChatModelAdapter(
  agentSlugRef: React.RefObject<string>,
  sessionIdRef: React.MutableRefObject<string | undefined>,
  onAgentEvent: React.RefObject<AgentEventCallback | undefined>,
  onRunStart: React.RefObject<((userText: string) => void) | undefined>,
): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      const sessionId = sessionIdRef.current;
      const lastUserMsg = messages.findLast((m) => m.role === "user");
      const text =
        lastUserMsg?.content.find((c) => c.type === "text")?.text ?? "";

      onRunStart.current?.(text);

      const res = await fetch(`${api.getApiBase()}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(api.getAuthToken()
            ? { Authorization: `Bearer ${api.getAuthToken()}` }
            : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          agent_slug: agentSlugRef.current,
        }),
        signal: abortSignal,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || res.statusText);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response stream");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (currentEvent === "session" && data.session_id) {
                sessionIdRef.current = data.session_id;
              } else if (currentEvent === "token" && data.content !== undefined) {
                accumulated += data.content;
                yield { content: [{ type: "text" as const, text: accumulated }] };
              } else if (
                currentEvent === "agent_start" ||
                currentEvent === "agent_token" ||
                currentEvent === "agent_done"
              ) {
                onAgentEvent.current?.(currentEvent, data);
              } else if (currentEvent === "error") {
                throw new Error(data.detail ?? "Agent error");
              }
            } catch (e) {
              if (e instanceof Error && e.message !== "Agent error") {
                /* skip malformed JSON */
              } else {
                throw e;
              }
            }
            currentEvent = "";
          } else if (line.trim() === "") {
            currentEvent = "";
          }
        }
      }
    },
  };
}

/* ------------------------------------------------------------------ */
/*  Build historical activity groups from loaded messages              */
/* ------------------------------------------------------------------ */

function buildActivityGroups(
  messages: { id: string; role: string; content: string; agent_activities?: AgentActivityRecord[] }[],
): ActivityGroup[] {
  const groups: ActivityGroup[] = [];
  const msgById = new Map(messages.map((m) => [m.id, m]));

  for (const msg of messages) {
    if (msg.role !== "assistant" || !msg.agent_activities?.length) continue;

    const triggerId = msg.agent_activities[0].trigger_message_id;
    const triggerMsg = msgById.get(triggerId);
    const triggerContent = triggerMsg?.content ?? "";

    groups.push({
      triggerMessageId: triggerId,
      triggerContent,
      agents: msg.agent_activities.map((a) => ({
        runId: a.run_id,
        slug: a.agent_slug,
        content: a.content,
        done: true,
      })),
    });
  }
  return groups;
}

/* ------------------------------------------------------------------ */
/*  History adapter                                                    */
/* ------------------------------------------------------------------ */

function useHistoryAdapter(
  remoteId: string | undefined,
  onActivitiesLoaded: React.RefObject<((groups: ActivityGroup[]) => void) | undefined>,
): ThreadHistoryAdapter {
  return useMemo(
    () => ({
      async load() {
        if (!remoteId) {
          onActivitiesLoaded.current?.([]);
          return ExportedMessageRepository.fromArray([]);
        }
        const msgs = await api.getChatSessionMessages(remoteId);

        const groups = buildActivityGroups(msgs as any);
        onActivitiesLoaded.current?.(groups);

        return ExportedMessageRepository.fromArray(
          msgs.map((m) => ({
            role: m.role as "user" | "assistant",
            content: [{ type: "text" as const, text: m.content }],
          })),
        );
      },
      async append() {},
    }),
    [remoteId, onActivitiesLoaded],
  );
}

function useThreadListAdapter(
  sessionIdRef: React.MutableRefObject<string | undefined>,
): unstable_RemoteThreadListAdapter {
  return useMemo(
    () => ({
      async list() {
        const sessions = await api.listChatSessions();
        return {
          threads: sessions.map((s) => ({
            status: (s.archived_at ? "archived" : "regular") as "regular" | "archived",
            remoteId: s.id,
            title: s.title,
          })),
        };
      },
      async initialize() {
        const session = await api.createChatSession();
        sessionIdRef.current = session.id;
        return { remoteId: session.id, externalId: undefined };
      },
      async rename(remoteId: string, newTitle: string) {
        await api.renameChatSession(remoteId, newTitle);
      },
      async archive(remoteId: string) {
        await api.archiveChatSession(remoteId);
      },
      async unarchive(remoteId: string) {
        await api.unarchiveChatSession(remoteId);
      },
      async delete(remoteId: string) {
        await api.deleteChatSession(remoteId);
      },
      async generateTitle(remoteId: string, messages: readonly any[]) {
        const firstUser = messages.find((m: any) => m.role === "user");
        const text =
          firstUser?.content?.find((c: any) => c.type === "text")?.text ?? "";
        const title = text.slice(0, 100) || "New chat";

        api.renameChatSession(remoteId, title).catch(() => {});

        const { createAssistantStream } = await import("assistant-stream");
        return createAssistantStream(async (controller) => {
          controller.appendText(title);
        });
      },
      async fetch(remoteId: string) {
        const sessions = await api.listChatSessions();
        const s = sessions.find((sess) => sess.id === remoteId);
        if (!s) throw new Error("Session not found");
        return {
          status: (s.archived_at ? "archived" : "regular") as "regular" | "archived",
          remoteId: s.id,
          title: s.title,
        };
      },
    }),
    [sessionIdRef],
  );
}

function RuntimeHook({
  agentSlugRef,
  sessionIdRef,
  onAgentEventRef,
  onActivitiesLoadedRef,
  onRunStartRef,
  onThreadSwitchRef,
}: {
  agentSlugRef: React.RefObject<string>;
  sessionIdRef: React.MutableRefObject<string | undefined>;
  onAgentEventRef: React.RefObject<AgentEventCallback | undefined>;
  onActivitiesLoadedRef: React.RefObject<((groups: ActivityGroup[]) => void) | undefined>;
  onRunStartRef: React.RefObject<((userText: string) => void) | undefined>;
  onThreadSwitchRef: React.RefObject<(() => void) | undefined>;
}) {
  const remoteId = useAuiState(
    (s: { threadListItem: { remoteId?: string } }) =>
      s.threadListItem.remoteId,
  );
  sessionIdRef.current = remoteId;

  useEffect(() => {
    onThreadSwitchRef.current?.();
  }, [remoteId, onThreadSwitchRef]);

  const history = useHistoryAdapter(remoteId, onActivitiesLoadedRef);
  const adapter = useMemo(
    () => makeChatModelAdapter(agentSlugRef, sessionIdRef, onAgentEventRef, onRunStartRef),
    [agentSlugRef, sessionIdRef, onAgentEventRef, onRunStartRef],
  );
  return useLocalRuntime(adapter, { adapters: { history } });
}

interface ContributrChatRuntimeProps extends PropsWithChildren {
  agentSlug: string;
}

export function ContributrChatRuntime({ children, agentSlug }: ContributrChatRuntimeProps) {
  const agentSlugRef = useRef(agentSlug);
  agentSlugRef.current = agentSlug;

  const sessionIdRef = useRef<string | undefined>(undefined);

  const [liveAgentMap, setLiveAgentMap] = useState<Map<string, ChildAgent>>(new Map());
  const [historicalActivities, setHistoricalActivities] = useState<ActivityGroup[]>([]);
  const [activityVisible, setActivityVisible] = useState(false);
  const [livePrompt, setLivePrompt] = useState("");
  const activeCountRef = useRef(0);

  const clearLive = useCallback(() => {
    setLiveAgentMap(new Map());
    setLivePrompt("");
    activeCountRef.current = 0;
  }, []);

  const resetActivity = useCallback(() => {
    setLiveAgentMap(new Map());
    setLivePrompt("");
    activeCountRef.current = 0;
    setHistoricalActivities([]);
    setActivityVisible(false);
  }, []);

  const onAgentEventRef = useRef<AgentEventCallback | undefined>(undefined);
  onAgentEventRef.current = (event: string, data: Record<string, string>) => {
    if (event === "agent_start") {
      activeCountRef.current += 1;
      if (activeCountRef.current >= 2) setActivityVisible(true);
      setLiveAgentMap((prev) => {
        const next = new Map(prev);
        next.set(data.run_id, { slug: data.slug, content: "", done: false });
        return next;
      });
    } else if (event === "agent_token") {
      setLiveAgentMap((prev) => {
        const next = new Map(prev);
        const agent = next.get(data.run_id);
        if (agent) {
          next.set(data.run_id, { ...agent, content: agent.content + data.content });
        }
        return next;
      });
    } else if (event === "agent_done") {
      activeCountRef.current = Math.max(0, activeCountRef.current - 1);
      setLiveAgentMap((prev) => {
        const next = new Map(prev);
        const agent = next.get(data.run_id);
        if (agent) {
          next.set(data.run_id, { ...agent, done: true });
        }
        return next;
      });
    }
  };

  const onActivitiesLoadedRef = useRef<((groups: ActivityGroup[]) => void) | undefined>(undefined);
  onActivitiesLoadedRef.current = (groups: ActivityGroup[]) => {
    clearLive();
    setHistoricalActivities(groups);
    setActivityVisible(groups.length > 0);
  };

  const onRunStartRef = useRef<((userText: string) => void) | undefined>(undefined);
  onRunStartRef.current = (userText: string) => {
    clearLive();
    setLivePrompt(userText);
  };

  const onThreadSwitchRef = useRef<(() => void) | undefined>(undefined);
  onThreadSwitchRef.current = () => {
    clearLive();
    setHistoricalActivities([]);
    setActivityVisible(false);
  };

  const ctxValue = useMemo<ChildAgentContextValue>(
    () => ({
      liveAgents: liveAgentMap,
      historicalActivities,
      activityVisible,
      setActivityVisible,
      clearLive,
      resetActivity,
      livePrompt,
    }),
    [liveAgentMap, historicalActivities, activityVisible, clearLive, resetActivity, livePrompt],
  );

  const threadListAdapter = useThreadListAdapter(sessionIdRef);
  const runtime = unstable_useRemoteThreadListRuntime({
    runtimeHook: () => RuntimeHook({ agentSlugRef, sessionIdRef, onAgentEventRef, onActivitiesLoadedRef, onRunStartRef, onThreadSwitchRef }),
    adapter: threadListAdapter,
  });

  return (
    <ChildAgentContext.Provider value={ctxValue}>
      <AssistantRuntimeProvider runtime={runtime}>
        {children}
      </AssistantRuntimeProvider>
    </ChildAgentContext.Provider>
  );
}
