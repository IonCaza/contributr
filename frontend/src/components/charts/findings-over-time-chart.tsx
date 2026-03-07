"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { format, parseISO } from "date-fns";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

interface RunPoint {
  run_id: string;
  date: string;
  dateLabel: string;
  findings: number;
  status: string;
}

const chartConfig = {
  findings: { label: "Findings", color: "var(--chart-1)" },
} satisfies ChartConfig;

interface FindingsOverTimeChartProps {
  runs: { id: string; started_at: string; findings_count: number; status: string }[];
  maxRuns?: number;
}

export function FindingsOverTimeChart({ runs, maxRuns = 24 }: FindingsOverTimeChartProps) {
  const data = useMemo(() => {
    const sorted = [...runs]
      .filter((r) => r.status === "completed" || r.status === "failed")
      .sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime())
      .slice(-maxRuns);

    return sorted.map((r) => {
      const d = parseISO(r.started_at);
      return {
        run_id: r.id,
        date: r.started_at,
        dateLabel: format(d, "MMM d, HH:mm"),
        findings: r.findings_count,
        status: r.status,
      } satisfies RunPoint;
    });
  }, [runs, maxRuns]);

  if (data.length < 2) return null;

  return (
    <div className="mt-4 pt-4 border-t">
      <p className="text-xs font-medium text-muted-foreground mb-3">Findings over time</p>
      <ChartContainer config={chartConfig} className="h-40 w-full">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="dateLabel"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis tickLine={false} axisLine={false} />
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value) => [`${value} findings`, "Findings"]}
                labelFormatter={(_, payload) => {
                  const p = payload?.[0]?.payload as RunPoint | undefined;
                  return p ? format(parseISO(p.date), "MMM d, yyyy 'at' HH:mm") : "";
                }}
              />
            }
          />
          <Bar
            dataKey="findings"
            fill="var(--color-findings)"
            radius={[4, 4, 0, 0]}
            maxBarSize={48}
          />
        </BarChart>
      </ChartContainer>
    </div>
  );
}
