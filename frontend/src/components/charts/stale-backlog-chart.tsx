"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

type StaleItem = { count: number } & ({ range: string } | { type: string });

const chartConfig = {
  count: { label: "Items", color: "hsl(25, 80%, 55%)" },
} satisfies ChartConfig;

export function StaleBacklogChart({
  data,
  title = "Stale Backlog (Days Since Last Update)",
}: {
  data: StaleItem[];
  title?: string;
}) {
  if (!data.length) return null;

  const labelKey = "range" in data[0] ? "range" : "type";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-48 w-full">
          <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey={labelKey} tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="count" fill="var(--color-count)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
