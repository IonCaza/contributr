"use client";

import { usePathname, useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const SUB_TABS = [
  { label: "Overview", value: "overview", href: "" },
  { label: "Pull Requests", value: "pull-requests", href: "/pull-requests" },
  { label: "Reviews", value: "reviews", href: "/reviews" },
] as const;

export function CodeSubTabs({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const basePath = `/projects/${projectId}/code`;

  let activeTab = "overview";
  if (pathname.startsWith(`${basePath}/pull-requests`)) activeTab = "pull-requests";
  else if (pathname.startsWith(`${basePath}/reviews`)) activeTab = "reviews";

  return (
    <Tabs
      value={activeTab}
      onValueChange={(v) => {
        const tab = SUB_TABS.find((t) => t.value === v);
        if (tab) router.push(`${basePath}${tab.href}`);
      }}
    >
      <TabsList variant="line">
        {SUB_TABS.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value}>
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
