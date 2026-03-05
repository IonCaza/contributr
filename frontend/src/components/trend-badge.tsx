"use client";

import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function TrendBadge({ value }: { value: number }) {
  const isUp = value > 0;
  const isDown = value < 0;

  return (
    <Badge
      variant="secondary"
      className={cn(
        "gap-1 font-mono text-xs",
        isUp && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
        isDown && "bg-red-500/10 text-red-600 dark:text-red-400",
        !isUp && !isDown && "bg-muted text-muted-foreground"
      )}
    >
      {isUp ? <ArrowUp className="h-3 w-3" /> : isDown ? <ArrowDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
      {Math.abs(value).toFixed(1)}%
    </Badge>
  );
}
