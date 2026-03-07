"use client";

import { Bar, BarChart, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

const HIERARCHY = ["epic", "feature", "user_story", "task", "bug"];
const LABELS: Record<string, string> = {
  epic: "Epic",
  feature: "Feature",
  user_story: "User Story",
  task: "Task",
  bug: "Bug",
};
const COLORS: Record<string, string> = {
  epic: "hsl(270, 70%, 55%)",
  feature: "hsl(210, 70%, 55%)",
  user_story: "hsl(150, 60%, 45%)",
  task: "hsl(45, 80%, 50%)",
  bug: "hsl(0, 70%, 55%)",
};

const chartConfig = {
  count: { label: "Count" },
} satisfies ChartConfig;

export function BacklogFunnelChart({
  data,
  title = "Backlog Hierarchy",
}: {
  data: { type: string; count: number }[];
  title?: string;
}) {
  if (!data.length) return null;

  const countMap = Object.fromEntries(data.map((d) => [d.type, d.count]));
  const ordered = HIERARCHY.filter((t) => (countMap[t] ?? 0) > 0).map((t) => ({
    type: LABELS[t] || t,
    count: countMap[t] || 0,
    fill: COLORS[t] || "var(--chart-1)",
  }));

  if (!ordered.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-48 w-full">
          <BarChart data={ordered} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
            <XAxis type="number" tickLine={false} axisLine={false} />
            <YAxis
              dataKey="type"
              type="category"
              tickLine={false}
              axisLine={false}
              width={80}
            />
            <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={28} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
