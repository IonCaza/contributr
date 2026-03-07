"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";

interface VelocityPoint {
  iteration: string;
  points: number;
  committed?: number;
}

const chartConfig = {
  points: { label: "Completed", color: "var(--chart-1)" },
  committed: { label: "Committed", color: "var(--chart-3)" },
} satisfies ChartConfig;

export function VelocityBarChart({
  data,
  title = "Velocity (Story Points per Sprint)",
}: {
  data: VelocityPoint[];
  title?: string;
}) {
  if (!data.length) return null;

  const hasCommitted = data.some((d) => d.committed != null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-64 w-full">
          <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="iteration"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: string) => (v.length > 12 ? v.slice(-12) : v)}
            />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            {hasCommitted && (
              <Bar dataKey="committed" fill="var(--color-committed)" radius={[4, 4, 0, 0]} />
            )}
            <Bar dataKey="points" fill="var(--color-points)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
