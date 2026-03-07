"use client";

import { use } from "react";
import { ProjectDeliveryTab } from "@/components/project-delivery-tab";

export default function ProjectDeliveryPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return <ProjectDeliveryTab projectId={projectId} />;
}
