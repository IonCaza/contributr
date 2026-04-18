"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

interface Bucket {
  range: string;
  count: number;
}

const chartConfig = {
  count: { label: "Work Items", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function CycleTimeHistogram({
  data,
  title = "Cycle Time Distribution",
  onBucketClick,
}: {
  data: Bucket[];
  title?: string;
  onBucketClick?: (bucket: Bucket) => void;
}) {
  if (!data.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-52 w-full">
          <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="range" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar
              dataKey="count"
              fill="var(--color-count)"
              radius={[4, 4, 0, 0]}
              cursor={onBucketClick ? "pointer" : undefined}
              onClick={onBucketClick ? (payload) => {
                const b = (payload as unknown as { payload?: Bucket }).payload;
                if (b) onBucketClick(b);
              } : undefined}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
