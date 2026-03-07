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

type CFDPoint = Record<string, string | number>;

const STATE_COLORS: Record<string, string> = {
  New: "hsl(45, 80%, 50%)",
  Active: "hsl(210, 70%, 55%)",
  Resolved: "hsl(150, 60%, 45%)",
  Closed: "hsl(220, 10%, 55%)",
};

export function CumulativeFlowChart({
  data,
  states,
  title = "Cumulative Flow",
}: {
  data: CFDPoint[];
  states: string[];
  title?: string;
}) {
  if (!data.length || !states.length) return null;

  const chartConfig: ChartConfig = {};
  for (const s of states) {
    chartConfig[s] = {
      label: s,
      color: STATE_COLORS[s] || `hsl(${(states.indexOf(s) * 60) % 360}, 60%, 50%)`,
    };
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-64 w-full">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            {states.map((s) => (
              <Area
                key={s}
                type="monotone"
                dataKey={s}
                stackId="cfd"
                stroke={`var(--color-${s})`}
                fill={`var(--color-${s})`}
                fillOpacity={0.4}
                dot={false}
              />
            ))}
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
