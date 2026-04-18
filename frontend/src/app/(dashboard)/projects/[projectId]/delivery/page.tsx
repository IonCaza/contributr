"use client";

import { use } from "react";
import { ProjectDeliveryTab } from "@/components/project-delivery-tab";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

export default function ProjectDeliveryPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  useRegisterUIContext("delivery", { project_id: projectId, page: "delivery" });

  return <ProjectDeliveryTab projectId={projectId} />;
}
