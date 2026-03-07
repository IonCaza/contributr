"use client";

import { Bar, BarChart, XAxis, YAxis, CartesianGrid } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

const STATE_COLORS: Record<string, string> = {
  New: "hsl(45, 80%, 50%)",
  Active: "hsl(210, 70%, 55%)",
  "In Progress": "hsl(210, 70%, 55%)",
  Committed: "hsl(190, 60%, 50%)",
  Approved: "hsl(170, 60%, 45%)",
  Resolved: "hsl(150, 60%, 45%)",
  Done: "hsl(150, 60%, 45%)",
  Completed: "hsl(150, 60%, 45%)",
  Closed: "hsl(220, 10%, 55%)",
};

const chartConfig = {
  count: { label: "Count" },
} satisfies ChartConfig;

export function BacklogStateChart({
  data,
  title = "Backlog by State",
}: {
  data: { state: string; count: number }[];
  title?: string;
}) {
  if (!data.length) return null;

  const formatted = data.map((d) => ({
    state: d.state,
    count: d.count,
    fill: STATE_COLORS[d.state] || "var(--chart-3)",
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-48 w-full">
          <BarChart data={formatted} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="state" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
