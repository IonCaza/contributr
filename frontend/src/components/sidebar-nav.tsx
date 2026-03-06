"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  LayoutDashboard, FolderGit2, Users, Settings, Sun, Moon,
  LogOut, ChevronLeft, ChevronRight, Bot,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderGit2 },
  { href: "/contributors", label: "Contributors", icon: Users },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface SidebarNavProps {
  aiEnabled: boolean;
  chatOpen: boolean;
  onChatToggle: () => void;
}

export function SidebarNav({ aiEnabled, chatOpen, onChatToggle }: SidebarNavProps) {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b px-4">
        {!collapsed && (
          <Link
            href="/dashboard"
            className="flex items-center gap-2 font-semibold tracking-tight"
          >
            <FolderGit2 className="h-5 w-5 text-primary" />
            <span>Contributr</span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn("ml-auto h-8 w-8", collapsed && "mx-auto")}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      <nav className="flex-1 space-y-1 p-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.href);
          const link = (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground",
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
          if (collapsed) {
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          }
          return link;
        })}
      </nav>

      <Separator />
      <div className="space-y-1 p-2">
        {aiEnabled &&
          (collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={chatOpen ? "secondary" : "ghost"}
                  size="icon"
                  className="w-full"
                  onClick={onChatToggle}
                >
                  <Bot className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">AI Assistant</TooltipContent>
            </Tooltip>
          ) : (
            <Button
              variant={chatOpen ? "secondary" : "ghost"}
              className="w-full justify-start gap-3"
              onClick={onChatToggle}
            >
              <Bot className="h-4 w-4" />
              <span>AI Assistant</span>
            </Button>
          ))}
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "default"}
          className={cn("w-full", !collapsed && "justify-start gap-3")}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
          {!collapsed && (
            <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          )}
        </Button>
        {user && (
          <Button
            variant="ghost"
            size={collapsed ? "icon" : "default"}
            className={cn(
              "w-full text-destructive hover:text-destructive",
              !collapsed && "justify-start gap-3",
            )}
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            {!collapsed && <span>Logout</span>}
          </Button>
        )}
      </div>
    </aside>
  );
}
