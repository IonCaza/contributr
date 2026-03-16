"use client";

import { usePathname } from "next/navigation";

export default function CodeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const isRepoSubRoute = pathname.includes("/repositories/");
  if (isRepoSubRoute) return <>{children}</>;

  return <div className="space-y-4">{children}</div>;
}
