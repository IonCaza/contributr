"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send, Plus, Trash2, Loader2, Bot, User as UserIcon,
  ChevronDown, MessageSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import type { ChatSession, ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  const hrs = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  if (days > 0) return `${days}d ago`;
  if (hrs > 0) return `${hrs}h ago`;
  if (mins > 0) return `${mins}m ago`;
  return "just now";
}

export function ChatPanel({ open, onClose }: ChatPanelProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const initialLoadRef = useRef(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamContent, scrollToBottom]);

  useEffect(() => {
    if (open && !initialLoadRef.current) {
      initialLoadRef.current = true;
      api.listChatSessions().then(setSessions).catch(() => {});
    }
  }, [open]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 150);
      return () => clearTimeout(t);
    }
  }, [open]);

  const loadSession = useCallback(async (sessionId: string) => {
    const msgs = await api.getChatSessionMessages(sessionId);
    setActiveSessionId(sessionId);
    setMessages(msgs);
  }, []);

  const startNewChat = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setStreamContent("");
    inputRef.current?.focus();
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      await api.deleteChatSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) startNewChat();
    },
    [activeSessionId, startNewChat],
  );

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setStreamContent("");

    await api.sendChatMessage(
      activeSessionId,
      text,
      (token) => setStreamContent((prev) => prev + token),
      (sessionId) => {
        setActiveSessionId(sessionId);
        api.listChatSessions().then(setSessions).catch(() => {});
      },
      (fullContent) => {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: fullContent,
            created_at: new Date().toISOString(),
          },
        ]);
        setStreamContent("");
        setStreaming(false);
      },
      (error) => {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Error: ${error}`,
            created_at: new Date().toISOString(),
          },
        ]);
        setStreamContent("");
        setStreaming(false);
      },
    );
  }, [input, streaming, activeSessionId]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage],
  );

  if (!open) return null;

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex h-10 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Contributr AI</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={startNewChat}
            title="New chat"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={onClose}
            title="Minimize"
          >
            <ChevronDown className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Body: sessions sidebar + chat area */}
      <div className="flex flex-1 min-h-0">
        {/* Sessions sidebar */}
        <div className="w-52 shrink-0 border-r flex flex-col">
          <div className="shrink-0 px-3 py-2 border-b">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              History
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-1.5">
            {sessions.length === 0 ? (
              <p className="px-2 py-4 text-xs text-muted-foreground text-center">
                No conversations yet
              </p>
            ) : (
              <div className="space-y-0.5">
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    className={cn(
                      "group flex items-center gap-2 rounded-md px-2 py-1.5 text-xs cursor-pointer transition-colors",
                      s.id === activeSessionId
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                    )}
                    onClick={() => loadSession(s.id)}
                  >
                    <MessageSquare className="h-3 w-3 shrink-0 opacity-60" />
                    <div className="flex-1 min-w-0">
                      <div className="truncate font-medium">{s.title}</div>
                      <div className="text-[10px] opacity-60">
                        {relativeTime(s.updated_at)}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 opacity-0 group-hover:opacity-100 shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSession(s.id);
                      }}
                    >
                      <Trash2 className="h-2.5 w-2.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {messages.length === 0 && !streamContent && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot className="mb-2 h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">
                  Ask anything about your contribution data
                </p>
                <p className="mt-1 text-xs text-muted-foreground/60">
                  Projects, repositories, contributors, commits, PRs, and statistics
                </p>
              </div>
            )}
            <div className="space-y-5 max-w-4xl">
              {messages
                .filter((m) => m.role !== "tool")
                .map((m) => (
                  <MessageBubble key={m.id} role={m.role} content={m.content} />
                ))}
              {streaming && streamContent && (
                <MessageBubble role="assistant" content={streamContent} />
              )}
              {streaming && !streamContent && (
                <div className="flex items-center gap-2 text-muted-foreground py-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              )}
            </div>
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="shrink-0 border-t px-4 py-3">
            <div className="flex gap-2 items-end max-w-4xl">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your data..."
                disabled={streaming}
                rows={1}
                className="flex-1 resize-none rounded-lg border bg-muted/40 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              />
              <Button
                size="icon"
                className="h-9 w-9 shrink-0"
                onClick={sendMessage}
                disabled={!input.trim() || streaming}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ role, content }: { role: string; content: string }) {
  const isUser = role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 mt-1">
          <Bot className="h-3.5 w-3.5 text-primary" />
        </div>
      )}
      <div
        className={cn(
          "rounded-lg text-sm",
          isUser
            ? "max-w-[70%] bg-primary px-4 py-2.5 text-primary-foreground"
            : "flex-1 min-w-0",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:mb-3 [&_p]:leading-relaxed [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5 [&_table]:my-3 [&_table]:text-xs [&_th]:px-3 [&_th]:py-1.5 [&_th]:text-left [&_td]:px-3 [&_td]:py-1.5 [&_pre]:my-3 [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:rounded-lg [&_code]:text-xs [&_code]:before:content-none [&_code]:after:content-none [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-2 [&_h3]:text-sm [&_h3]:font-medium [&_h3]:mt-2 [&_h3]:mb-1 [&_blockquote]:border-l-primary/30 [&_blockquote]:text-muted-foreground [&_hr]:my-4 [&_strong]:font-semibold">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}
      </div>
      {isUser && (
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary mt-1">
          <UserIcon className="h-3.5 w-3.5 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}
