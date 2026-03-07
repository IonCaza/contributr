"use client";

import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";

interface ThroughputPoint {
  date: string;
  created: number;
  completed: number;
}

const chartConfig = {
  created: { label: "Created", color: "var(--chart-4)" },
  completed: { label: "Completed", color: "var(--chart-2)" },
} satisfies ChartConfig;

export function ThroughputChart({
  data,
  title = "Throughput (Created vs Completed)",
}: {
  data: ThroughputPoint[];
  title?: string;
}) {
  if (!data.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-64 w-full">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="throughputCreated" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-created)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="var(--color-created)" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="throughputCompleted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-completed)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="var(--color-completed)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Area
              type="monotone"
              dataKey="created"
              stroke="var(--color-created)"
              fill="url(#throughputCreated)"
              strokeWidth={2}
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="completed"
              stroke="var(--color-completed)"
              fill="url(#throughputCompleted)"
              strokeWidth={2}
              dot={false}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
