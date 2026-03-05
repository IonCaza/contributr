"use client";

import { useId } from "react";
import { ResponsiveContainer, AreaChart, Area } from "recharts";

export function MiniSparkline({ data, color = "var(--chart-1)" }: { data: number[]; color?: string }) {
  const uid = useId();
  const chartData = data.map((v, i) => ({ i, v }));
  const gradientId = `spark-${uid}`;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#${gradientId})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
