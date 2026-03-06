"use client";

import { Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { TrendBadge } from "@/components/trend-badge";
import { MiniSparkline } from "@/components/charts/mini-sparkline";

interface StatCardProps {
  title: string;
  value: string | number;
  trend?: number;
  sparklineData?: number[];
  subtitle?: string;
  tooltip?: string;
  onClick?: () => void;
}

export function StatCard({ title, value, trend, sparklineData, subtitle, tooltip, onClick }: StatCardProps) {
  return (
    <Card
      className={onClick ? "cursor-pointer transition-colors hover:border-primary/40 hover:bg-muted/40" : undefined}
      onClick={onClick}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-1.5">
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
          {tooltip && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <Info className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 hover:text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-60">
                  {tooltip}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
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
