"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";

export interface ChatRequest {
  agentSlug: string;
  message: string;
}

interface ChatTriggerContextValue {
  pending: ChatRequest | null;
  consume: () => ChatRequest | null;
  openChat: (agentSlug: string, message: string) => void;
}

const ChatTriggerContext = createContext<ChatTriggerContextValue>({
  pending: null,
  consume: () => null,
  openChat: () => {},
});

export function useChatTriggerProvider(onOpen: () => void) {
  const [pending, setPending] = useState<ChatRequest | null>(null);
  const pendingRef = useRef<ChatRequest | null>(null);

  const openChat = useCallback(
    (agentSlug: string, message: string) => {
      const req = { agentSlug, message };
      pendingRef.current = req;
      setPending(req);
      onOpen();
    },
    [onOpen],
  );

  const consume = useCallback(() => {
    const req = pendingRef.current;
    pendingRef.current = null;
    setPending(null);
    return req;
  }, []);

  return { value: { pending, consume, openChat }, Provider: ChatTriggerContext.Provider };
}

export function useChatTrigger() {
  return useContext(ChatTriggerContext);
}
