"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { SidebarNav } from "@/components/sidebar-nav";
import { ChatPanel } from "@/components/chat-panel";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
  type PanelImperativeHandle,
} from "@/components/ui/resizable";
import { api } from "@/lib/api-client";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [chatOpen, setChatOpen] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const chatPanelRef = useRef<PanelImperativeHandle>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api
        .getAiStatus()
        .then((s) => setAiEnabled(s.enabled && s.configured))
        .catch(() => {});
    }
  }, [user]);

  const handleChatToggle = useCallback(() => {
    if (chatOpen) {
      chatPanelRef.current?.collapse();
    } else {
      chatPanelRef.current?.resize("40%");
    }
  }, [chatOpen]);

  const handleChatClose = useCallback(() => {
    chatPanelRef.current?.collapse();
  }, []);

  const handleChatPanelResize = useCallback(() => {
    const collapsed = chatPanelRef.current?.isCollapsed() ?? true;
    setChatOpen(!collapsed);
  }, []);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <SidebarNav
        aiEnabled={aiEnabled}
        chatOpen={chatOpen}
        onChatToggle={handleChatToggle}
      />
      <ResizablePanelGroup orientation="vertical" className="flex-1 min-w-0">
        <ResizablePanel id="main" defaultSize="100%" minSize="20%">
          <main className="h-full overflow-y-auto bg-background p-6">
            {children}
          </main>
        </ResizablePanel>
        <ResizableHandle className="h-[3px] bg-transparent transition-colors hover:bg-accent/50 data-[separator]:hover:bg-accent/50" />
        <ResizablePanel
          id="chat"
          panelRef={chatPanelRef}
          defaultSize="0%"
          minSize="15%"
          maxSize="80%"
          collapsible
          onResize={handleChatPanelResize}
        >
          <ChatPanel open={chatOpen} onClose={handleChatClose} />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
