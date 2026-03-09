"use client";

import { Bot, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { ContributrChatRuntime } from "@/components/contributr-chat-runtime";
import { useAgents } from "@/hooks/use-settings";
import { useState } from "react";

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
}

export function ChatPanel({ open, onClose }: ChatPanelProps) {
  const { data: agents = [] } = useAgents();
  const enabledAgents = agents.filter((a) => a.enabled);
  const [agentSlug, setAgentSlug] = useState("contribution-analyst");

  if (!open) return <div className="h-full bg-background" />;

  return (
    <ContributrChatRuntime agentSlug={agentSlug}>
      <div className="flex h-full flex-col bg-background">
        <div className="flex h-10 shrink-0 items-center justify-between border-b px-4">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            {enabledAgents.length > 1 ? (
              <Select value={agentSlug} onValueChange={setAgentSlug}>
                <SelectTrigger className="h-7 w-auto border-0 bg-transparent py-0 px-1.5 text-sm font-semibold shadow-none focus:ring-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {enabledAgents.map((a) => (
                    <SelectItem key={a.slug} value={a.slug}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <span className="text-sm font-semibold">
                {enabledAgents[0]?.name || "Contributr AI"}
              </span>
            )}
          </div>
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

        <div className="flex flex-1 min-h-0">
          <div className="w-52 shrink-0 overflow-y-auto border-r p-2">
            <ThreadList />
          </div>
          <div className="flex-1 min-w-0">
            <Thread />
          </div>
        </div>
      </div>
    </ContributrChatRuntime>
  );
}
