"use client";

import { type PropsWithChildren, useMemo, useRef } from "react";
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

function makeChatModelAdapter(
  agentSlugRef: React.RefObject<string>,
  sessionIdRef: React.RefObject<string | undefined>,
): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      const sessionId = sessionIdRef.current;
      const lastUserMsg = messages.findLast((m) => m.role === "user");
      const text =
        lastUserMsg?.content.find((c) => c.type === "text")?.text ?? "";

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
              if (currentEvent === "token" && data.content !== undefined) {
                accumulated += data.content;
                yield { content: [{ type: "text" as const, text: accumulated }] };
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

function useHistoryAdapter(remoteId: string | undefined): ThreadHistoryAdapter {
  return useMemo(
    () => ({
      async load() {
        if (!remoteId) return ExportedMessageRepository.fromArray([]);
        const msgs = await api.getChatSessionMessages(remoteId);
        return ExportedMessageRepository.fromArray(
          msgs.map((m) => ({
            role: m.role as "user" | "assistant",
            content: [{ type: "text" as const, text: m.content }],
          })),
        );
      },
      async append() {},
    }),
    [remoteId],
  );
}

function useThreadListAdapter(): unstable_RemoteThreadListAdapter {
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
      async generateTitle(_remoteId: string, messages: readonly any[]) {
        const firstUser = messages.find((m: any) => m.role === "user");
        const text =
          firstUser?.content?.find((c: any) => c.type === "text")?.text ?? "";
        const title = text.slice(0, 80) || "New chat";

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
    [],
  );
}

function RuntimeHook({ agentSlugRef }: { agentSlugRef: React.RefObject<string> }) {
  const remoteId = useAuiState(
    (s: { threadListItem: { remoteId?: string } }) =>
      s.threadListItem.remoteId,
  );
  const sessionIdRef = useRef<string | undefined>(remoteId);
  sessionIdRef.current = remoteId;

  const history = useHistoryAdapter(remoteId);
  const adapter = useMemo(
    () => makeChatModelAdapter(agentSlugRef, sessionIdRef),
    [agentSlugRef, sessionIdRef],
  );
  return useLocalRuntime(adapter, { adapters: { history } });
}

interface ContributrChatRuntimeProps extends PropsWithChildren {
  agentSlug: string;
}

export function ContributrChatRuntime({ children, agentSlug }: ContributrChatRuntimeProps) {
  const agentSlugRef = useRef(agentSlug);
  agentSlugRef.current = agentSlug;

  const threadListAdapter = useThreadListAdapter();
  const runtime = unstable_useRemoteThreadListRuntime({
    runtimeHook: () => RuntimeHook({ agentSlugRef }),
    adapter: threadListAdapter,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
