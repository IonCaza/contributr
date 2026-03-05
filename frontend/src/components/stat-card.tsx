"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendBadge } from "@/components/trend-badge";
import { MiniSparkline } from "@/components/charts/mini-sparkline";

interface StatCardProps {
  title: string;
  value: string | number;
  trend?: number;
  sparklineData?: number[];
  subtitle?: string;
}

export function StatCard({ title, value, trend, sparklineData, subtitle }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {trend !== undefined && <TrendBadge value={trend} />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{typeof value === "number" ? value.toLocaleString() : value}</div>
        {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        {sparklineData && sparklineData.length > 1 && (
          <div className="mt-3 h-10">
            <MiniSparkline data={sparklineData} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
