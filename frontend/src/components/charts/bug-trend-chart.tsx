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

interface BugTrendPoint {
  date: string;
  created: number;
  resolved: number;
}

const chartConfig = {
  created: { label: "Bugs Created", color: "hsl(0, 70%, 55%)" },
  resolved: { label: "Bugs Resolved", color: "hsl(150, 60%, 45%)" },
} satisfies ChartConfig;

export function BugTrendChart({
  data,
  title = "Bug Trend (Created vs Resolved)",
}: {
  data: BugTrendPoint[];
  title?: string;
}) {
  if (!data.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-52 w-full">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="bugCreated" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-created)" stopOpacity={0.3} />
                <stop offset="100%" stopColor="var(--color-created)" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="bugResolved" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-resolved)" stopOpacity={0.3} />
                <stop offset="100%" stopColor="var(--color-resolved)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Area type="monotone" dataKey="created" stroke="var(--color-created)" fill="url(#bugCreated)" strokeWidth={2} dot={false} />
            <Area type="monotone" dataKey="resolved" stroke="var(--color-resolved)" fill="url(#bugResolved)" strokeWidth={2} dot={false} />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
