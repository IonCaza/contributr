"use client";

import { use } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useProject } from "@/hooks/use-projects";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Code", href: "code" },
  { label: "Delivery", href: "delivery" },
  { label: "Security", href: "security" },
  { label: "Dependencies", href: "dependencies" },
  { label: "Standards", href: "adrs" },
  { label: "Presentations", href: "presentations" },
  { label: "Insights", href: "insights" },
  { label: "Settings", href: "settings" },
] as const;

export default function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const pathname = usePathname();
  const { data: project } = useProject(projectId);

  const isSubRoute = pathname.includes("/repositories/");

  if (isSubRoute) {
    return (
      <div className="space-y-6">
        <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
          {project ? (
            <Link href={`/projects/${projectId}/code`} className="hover:text-foreground transition-colors">
              {project.name}
            </Link>
          ) : (
            <Skeleton className="h-4 w-32" />
          )}
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-foreground font-medium">Repository</span>
        </nav>
        <div>{children}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        {project ? (
          <>
            <h1 className="text-3xl font-bold tracking-tight">{project.name}</h1>
            {project.description && (
              <p className="text-muted-foreground">{project.description}</p>
            )}
          </>
        ) : (
          <div className="space-y-2">
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-5 w-72" />
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 border-b border-border">
        {TABS.map((tab) => {
          const tabPath = `/projects/${projectId}/${tab.href}`;
          const isActive = pathname.startsWith(tabPath);
          return (
            <Link
              key={tab.href}
              href={tabPath}
              className={cn(
                "relative px-4 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
              {isActive && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 bg-primary rounded-full" />
              )}
            </Link>
          );
        })}
      </div>

      <div>{children}</div>
    </div>
  );
}
