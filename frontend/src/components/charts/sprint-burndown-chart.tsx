"use client";

import { useMemo } from "react";
import { Line, LineChart, CartesianGrid, XAxis, YAxis, ReferenceLine, Label } from "recharts";
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
  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }, []);

  const showToday = data.length >= 2 && todayStr >= data[0].date && todayStr <= data[data.length - 1].date;

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
            {showToday && (
              <ReferenceLine
                x={todayStr}
                stroke="var(--primary)"
                strokeDasharray="4 3"
                strokeWidth={1.5}
              >
                <Label
                  value="Today"
                  position="top"
                  fill="var(--primary)"
                  fontSize={11}
                  fontWeight={600}
                />
              </ReferenceLine>
            )}
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
