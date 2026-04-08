"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  LayoutDashboard, FolderGit2, Users, Users2, Settings, Sun, Moon,
  LogOut, ChevronLeft, ChevronRight, Bot, MoreHorizontal, User as UserIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderGit2 },
  { href: "/contributors", label: "Contributors", icon: Users },
  { href: "/teams", label: "Teams", icon: Users2 },
];

interface SidebarNavProps {
  aiEnabled: boolean;
  chatOpen: boolean;
  onChatToggle: () => void;
}

function UserSection({ user, pathname, collapsed, logout }: {
  user: { username?: string; full_name?: string | null };
  pathname: string;
  collapsed: boolean;
  logout: () => void;
}) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const profileActive = pathname.startsWith("/profile");

  const menuItems = (
    <DropdownMenuContent side="right" align="end" className="w-48">
      {collapsed && (
        <>
          <DropdownMenuItem onClick={() => router.push("/profile")}>
            <UserIcon className="mr-2 h-4 w-4" /> Profile
          </DropdownMenuItem>
          <DropdownMenuSeparator />
        </>
      )}
      <DropdownMenuItem onClick={() => router.push("/settings")}>
        <Settings className="mr-2 h-4 w-4" /> Settings
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
        {theme === "dark"
          ? <><Sun className="mr-2 h-4 w-4" /> Light mode</>
          : <><Moon className="mr-2 h-4 w-4" /> Dark mode</>}
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
        <LogOut className="mr-2 h-4 w-4" /> Logout
      </DropdownMenuItem>
    </DropdownMenuContent>
  );

  if (collapsed) {
    return (
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "relative flex w-full items-center justify-center rounded-md py-2 transition-all duration-150",
                  profileActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "hover:bg-sidebar-accent/50",
                )}
              >
                {profileActive && (
                  <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
                )}
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
                  {user.username?.charAt(0).toUpperCase() ?? "U"}
                </div>
              </button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent side="right">{user.full_name || user.username}</TooltipContent>
        </Tooltip>
        {menuItems}
      </DropdownMenu>
    );
  }

  return (
    <div
      className={cn(
        "relative flex items-center gap-2 rounded-md px-3 py-2 transition-all duration-150",
        profileActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "hover:bg-sidebar-accent/50",
      )}
    >
      {profileActive && (
        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
      )}
      <Link href="/profile" className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
          {user.username?.charAt(0).toUpperCase() ?? "U"}
        </div>
        <div className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-sidebar-foreground">{user.full_name || user.username}</span>
          <span className="block truncate text-xs text-sidebar-foreground/50">@{user.username}</span>
        </div>
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors">
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        {menuItems}
      </DropdownMenu>
    </div>
  );
}

export function SidebarNav({ aiEnabled, chatOpen, onChatToggle }: SidebarNavProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "flex h-screen flex-col overflow-hidden border-r bg-sidebar text-sidebar-foreground transition-all duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
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
                "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all duration-150",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
              )}
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
        {user && (
          <>
            {aiEnabled && <Separator className="!my-2" />}
            <UserSection
              user={user}
              pathname={pathname}
              collapsed={collapsed}
              logout={logout}
            />
          </>
        )}
      </div>
    </aside>
  );
}
