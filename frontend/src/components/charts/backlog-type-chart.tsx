"use client";

import { Bar, BarChart, XAxis, YAxis, CartesianGrid } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

const TYPE_LABELS: Record<string, string> = {
  epic: "Epic",
  feature: "Feature",
  user_story: "User Story",
  task: "Task",
  bug: "Bug",
};

const TYPE_COLORS: Record<string, string> = {
  epic: "hsl(270, 70%, 55%)",
  feature: "hsl(210, 70%, 55%)",
  user_story: "hsl(150, 60%, 45%)",
  task: "hsl(45, 80%, 50%)",
  bug: "hsl(0, 70%, 55%)",
};

const chartConfig = {
  count: { label: "Count" },
} satisfies ChartConfig;

export function BacklogTypeChart({
  data,
  title = "Backlog by Type",
  onTypeClick,
}: {
  data: { type: string; count: number }[];
  title?: string;
  onTypeClick?: (type: string) => void;
}) {
  if (!data.length) return null;

  const formatted = data
    .map((d) => ({
      type: TYPE_LABELS[d.type] || d.type,
      rawType: d.type,
      count: d.count,
      fill: TYPE_COLORS[d.type] || "var(--chart-1)",
    }))
    .sort((a, b) => b.count - a.count);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-48 w-full">
          <BarChart data={formatted} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid horizontal={false} />
            <YAxis
              dataKey="type"
              type="category"
              tickLine={false}
              axisLine={false}
              width={80}
            />
            <XAxis type="number" tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
            <Bar
              dataKey="count"
              radius={[0, 4, 4, 0]}
              cursor={onTypeClick ? "pointer" : undefined}
              onClick={onTypeClick ? (payload) => {
                const p = (payload as unknown as { payload?: { rawType: string } }).payload;
                if (p?.rawType) onTypeClick(p.rawType);
              } : undefined}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
