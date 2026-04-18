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
};

const chartConfig = {
  count: { label: "Items", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function WIPChart({
  data,
  title = "Work In Progress",
  onStateClick,
}: {
  data: { state: string; count: number }[];
  title?: string;
  onStateClick?: (state: string) => void;
}) {
  if (!data.length) return null;

  const formatted = data.map((d) => ({
    ...d,
    fill: STATE_COLORS[d.state] || "var(--chart-1)",
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
            <Bar
              dataKey="count"
              radius={[4, 4, 0, 0]}
              cursor={onStateClick ? "pointer" : undefined}
              onClick={onStateClick ? (payload) => {
                const p = (payload as unknown as { payload?: { state: string } }).payload;
                if (p?.state) onStateClick(p.state);
              } : undefined}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
