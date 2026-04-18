"use client";

import { useMemo } from "react";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useBacklogSizingTrend } from "@/hooks/use-delivery";
import { cn } from "@/lib/utils";

const BUCKET_COLORS: Record<string, string> = {
  "Unsized": "var(--chart-5)",
  "1": "var(--chart-1)",
  "2-3": "var(--chart-2)",
  "5": "var(--chart-3)",
  "8": "var(--chart-4)",
  "13+": "var(--destructive)",
};

export function SizingTrendCard({
  projectId,
  teamId,
  title = "Sizing distribution trend",
  weeks = 16,
}: {
  projectId: string;
  teamId?: string;
  title?: string;
  weeks?: number;
}) {
  const { data, isLoading } = useBacklogSizingTrend(projectId, { team_id: teamId, weeks });

  const { chartData, totalItems, overallAvg } = useMemo(() => {
    if (!data) {
      return { chartData: [] as Record<string, number | string | null>[], totalItems: 0, overallAvg: null as number | null };
    }
    const rows = data.series.map((w) => {
      const row: Record<string, number | string | null> = {
        week: w.week_start.slice(5), // MM-DD
        avg: w.avg_points,
      };
      for (const b of data.bucket_order) {
        row[b] = w.buckets[b] ?? 0;
      }
      return row;
    });
    const total = Object.values(data.totals).reduce((s, n) => s + n, 0);
    const sumAvg = data.series.reduce((s, w) => s + (w.avg_points ?? 0), 0);
    const avgWeeks = data.series.filter((w) => w.avg_points !== null).length;
    const overall = avgWeeks > 0 ? sumAvg / avgWeeks : null;
    return { chartData: rows, totalItems: total, overallAvg: overall };
  }, [data]);

  const slope = data?.avg_points_trend_slope ?? null;
  const trendDirection: "shrinking" | "growing" | "flat" | "unknown" =
    slope === null ? "unknown"
      : slope <= -0.05 ? "shrinking"
        : slope >= 0.05 ? "growing"
          : "flat";

  const TrendIcon = trendDirection === "shrinking"
    ? TrendingDown
    : trendDirection === "growing"
      ? TrendingUp
      : Minus;

  const trendColor = trendDirection === "shrinking"
    ? "text-emerald-600"
    : trendDirection === "growing"
      ? "text-red-600"
      : "text-muted-foreground";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {data && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {totalItems} stories over {data.weeks} weeks · avg {overallAvg?.toFixed(1) ?? "—"} SP overall
              </p>
            )}
          </div>
          {trendDirection !== "unknown" && (
            <Badge variant="outline" className={cn("text-[11px] flex items-center gap-1", trendColor)}>
              <TrendIcon className="h-3 w-3" />
              {trendDirection}
              {slope !== null && (
                <span className="font-mono ml-1">{slope > 0 ? "+" : ""}{slope.toFixed(2)}/w</span>
              )}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !data || chartData.length === 0 ? (
          <p className="text-sm text-muted-foreground">Not enough sized stories to compute a trend.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData} margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {data.bucket_order.map((b) => (
                <Bar
                  key={b}
                  yAxisId="left"
                  dataKey={b}
                  name={b === "Unsized" ? "Unsized" : `${b} SP`}
                  stackId="s"
                  fill={BUCKET_COLORS[b] ?? "var(--chart-5)"}
                />
              ))}
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="avg"
                name="Avg SP"
                stroke="currentColor"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
