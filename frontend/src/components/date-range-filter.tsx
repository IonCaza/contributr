"use client";

import { useState } from "react";
import { CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const PRESETS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "1y", days: 365 },
  { label: "All", days: 0 },
] as const;

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export interface DateRange {
  from: string;
  to: string;
}

interface Props {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

export function defaultRange(): DateRange {
  return { from: daysAgo(90), to: today() };
}

export function DateRangeFilter({ value, onChange }: Props) {
  const [customOpen, setCustomOpen] = useState(false);

  const activePreset = PRESETS.find((p) => {
    if (p.days === 0) return value.from === "" || value.from <= daysAgo(3650);
    return value.from === daysAgo(p.days) && value.to === today();
  });

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <CalendarDays className="h-4 w-4 text-muted-foreground" />
      <div className="flex rounded-md border border-border overflow-hidden">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            onClick={() => {
              onChange({
                from: p.days === 0 ? daysAgo(3650) : daysAgo(p.days),
                to: today(),
              });
              setCustomOpen(false);
            }}
            className={`px-3 py-1 text-xs font-medium transition-colors border-r border-border last:border-r-0 ${
              activePreset?.label === p.label
                ? "bg-primary text-primary-foreground"
                : "bg-background text-foreground hover:bg-accent"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      <Button
        variant={customOpen ? "secondary" : "ghost"}
        size="sm"
        className="text-xs h-7"
        onClick={() => setCustomOpen((v) => !v)}
      >
        Custom
      </Button>
      {customOpen && (
        <div className="flex items-center gap-1.5">
          <Input
            type="date"
            value={value.from}
            onChange={(e) => onChange({ ...value, from: e.target.value })}
            className="h-7 w-32 text-xs"
          />
          <span className="text-xs text-muted-foreground">to</span>
          <Input
            type="date"
            value={value.to}
            onChange={(e) => onChange({ ...value, to: e.target.value })}
            className="h-7 w-32 text-xs"
          />
        </div>
      )}
    </div>
  );
}
