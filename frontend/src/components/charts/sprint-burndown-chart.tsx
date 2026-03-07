"use client";

import { Line, LineChart, CartesianGrid, XAxis, YAxis, ReferenceLine } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";

interface BurndownPoint {
  date: string;
  remaining: number;
  ideal: number;
}

const chartConfig = {
  remaining: { label: "Remaining", color: "var(--chart-1)" },
  ideal: { label: "Ideal", color: "var(--chart-3)" },
} satisfies ChartConfig;

export function SprintBurndownChart({
  data,
  title = "Sprint Burndown",
}: {
  data: BurndownPoint[];
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
          <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ReferenceLine y={0} stroke="var(--border)" />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Line
              type="monotone"
              dataKey="ideal"
              stroke="var(--color-ideal)"
              strokeWidth={1.5}
              strokeDasharray="6 3"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="remaining"
              stroke="var(--color-remaining)"
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5, strokeWidth: 2 }}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
