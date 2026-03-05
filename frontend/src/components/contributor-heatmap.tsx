"use client";

import { useMemo } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface HeatmapProps {
  data: Record<string, number>;
  title?: string;
}

function getIntensity(count: number, max: number): string {
  if (count === 0) return "bg-muted";
  const ratio = count / max;
  if (ratio < 0.25) return "bg-emerald-200 dark:bg-emerald-900";
  if (ratio < 0.5) return "bg-emerald-400 dark:bg-emerald-700";
  if (ratio < 0.75) return "bg-emerald-500 dark:bg-emerald-500";
  return "bg-emerald-700 dark:bg-emerald-400";
}

export function ContributorHeatmap({ data, title = "Contribution Activity" }: HeatmapProps) {
  const { weeks, maxCount } = useMemo(() => {
    const today = new Date();
    const daysBack = 365;
    const start = new Date(today);
    start.setDate(start.getDate() - daysBack);
    start.setDate(start.getDate() - start.getDay());

    const allWeeks: { date: Date; count: number }[][] = [];
    let currentWeek: { date: Date; count: number }[] = [];
    let max = 0;

    const cursor = new Date(start);
    while (cursor <= today) {
      const key = cursor.toISOString().slice(0, 10);
      const count = data[key] || 0;
      if (count > max) max = count;
      currentWeek.push({ date: new Date(cursor), count });
      if (currentWeek.length === 7) {
        allWeeks.push(currentWeek);
        currentWeek = [];
      }
      cursor.setDate(cursor.getDate() + 1);
    }
    if (currentWeek.length > 0) allWeeks.push(currentWeek);
    return { weeks: allWeeks, maxCount: max || 1 };
  }, [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-0.5 overflow-x-auto pb-2">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5">
              {week.map((day) => {
                const label = `${day.date.toLocaleDateString()}: ${day.count} contributions`;
                return (
                  <Tooltip key={day.date.toISOString()}>
                    <TooltipTrigger>
                      <div className={cn("h-3 w-3 rounded-sm", getIntensity(day.count, maxCount))} />
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">{label}</TooltipContent>
                  </Tooltip>
                );
              })}
            </div>
          ))}
        </div>
        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <span>Less</span>
          {[0, 0.25, 0.5, 0.75, 1].map((r) => (
            <div key={r} className={cn("h-3 w-3 rounded-sm", getIntensity(r * 10, 10))} />
          ))}
          <span>More</span>
        </div>
      </CardContent>
    </Card>
  );
}
