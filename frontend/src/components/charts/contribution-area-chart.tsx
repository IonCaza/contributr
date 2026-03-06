"use client";

import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DataPoint {
  date: string;
  lines_added: number;
  lines_deleted: number;
  commits: number;
}

const COLORS = {
  added: "var(--chart-2)",
  deleted: "var(--chart-5)",
  commits: "var(--chart-1)",
};

export function ContributionAreaChart({ data, title, seriesNames }: { data: DataPoint[]; title?: string; seriesNames?: { added?: string; deleted?: string } }) {
  const addedLabel = seriesNames?.added ?? "Lines added";
  const deletedLabel = seriesNames?.deleted ?? "Lines deleted";
  const hideSeries2 = data.every((d) => d.lines_deleted === 0);
  return (
    <Card>
      {title && (
        <CardHeader>
          <CardTitle className="text-base">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className={title ? "" : "pt-6"}>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="addedGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.added} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={COLORS.added} stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="deletedGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.deleted} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={COLORS.deleted} stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.5} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} stroke="var(--border)" />
              <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} stroke="var(--border)" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  color: "var(--popover-foreground)",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                }}
                itemStyle={{ color: "var(--popover-foreground)" }}
                labelStyle={{ color: "var(--muted-foreground)", fontWeight: 600, marginBottom: 4 }}
              />
              <Area type="monotone" dataKey="lines_added" name={addedLabel} stroke={COLORS.added} fill="url(#addedGrad)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2 }} />
              {!hideSeries2 && (
                <Area type="monotone" dataKey="lines_deleted" name={deletedLabel} stroke={COLORS.deleted} fill="url(#deletedGrad)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2 }} />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
