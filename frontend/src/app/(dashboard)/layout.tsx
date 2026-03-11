"use client";

import { useRef, useState, useCallback, useEffect } from "react";
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
import { useAiStatus } from "@/hooks/use-settings";
import { FeedbackWidget } from "@/components/feedback-widget";
import { MfaSetupDialog } from "@/components/mfa-setup-dialog";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();
  const [chatOpen, setChatOpen] = useState(false);
  const chatPanelRef = useRef<PanelImperativeHandle>(null);

  const { data: aiStatusData } = useAiStatus();
  const aiEnabled = !!(aiStatusData?.enabled && aiStatusData?.configured);

  const needsMfaSetup = user?.mfa_setup_required ?? false;

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  const handleChatToggle = useCallback(() => {
    if (chatOpen) {
      chatPanelRef.current?.collapse();
    } else {
      chatPanelRef.current?.expand();
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
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm text-muted-foreground">Loading...</span>
        </div>
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
      <ResizablePanelGroup orientation="vertical" className="flex-1 min-w-0 h-full overflow-hidden">
        <ResizablePanel id="main" defaultSize="100%" minSize="20%">
          <main className="h-full overflow-y-auto bg-background p-6">
            {children}
          </main>
        </ResizablePanel>
        <ResizableHandle className="group relative h-2 bg-border/40 transition-colors hover:bg-accent/60 active:bg-accent">
          <div className="absolute inset-x-0 top-1/2 flex -translate-y-1/2 items-center justify-center">
            <div className="h-1 w-12 rounded-full bg-muted-foreground/30 transition-colors group-hover:bg-muted-foreground/60 group-active:bg-muted-foreground/80" />
          </div>
        </ResizableHandle>
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
      <FeedbackWidget />
      {needsMfaSetup && (
        <MfaSetupDialog
          open
          dismissible={false}
          onComplete={async (at, rt) => {
            localStorage.setItem("access_token", at);
            localStorage.setItem("refresh_token", rt);
            await refresh();
          }}
        />
      )}
    </div>
  );
}
