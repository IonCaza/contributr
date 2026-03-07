"use client";

import { useState } from "react";
import {
  AlertTriangle, AlertCircle, Info,
  ChevronDown, ChevronRight, X, Clock,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ConfirmDialog } from "@/components/confirm-dialog";
import type { InsightFinding } from "@/lib/types";

export const SEVERITY_CONFIG: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  critical: { icon: AlertTriangle, color: "text-red-500", bg: "bg-red-500/10" },
  warning: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-500/10" },
  info: { icon: Info, color: "text-blue-500", bg: "bg-blue-500/10" },
};

export const CATEGORY_LABELS: Record<string, string> = {
  process: "Process",
  delivery: "Delivery",
  team_balance: "Team",
  code_quality: "Code Quality",
  intersection: "Intersection",
};

export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatMetricKey(key: string): string {
  return key.replace(/_/g, " ").replace(/pct$/i, "%");
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
}

function MetricDataView({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(
    ([, v]) => v !== null && v !== undefined && !Array.isArray(v) && typeof v !== "object",
  );
  const listEntries = Object.entries(data).filter(
    ([, v]) => Array.isArray(v),
  );

  if (entries.length === 0 && listEntries.length === 0) return null;

  return (
    <div className="space-y-2">
      {entries.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {entries.map(([k, v]) => (
            <div key={k} className="rounded-md bg-muted/30 px-2.5 py-1.5">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{formatMetricKey(k)}</p>
              <p className="text-sm font-medium">{formatMetricValue(v)}</p>
            </div>
          ))}
        </div>
      )}
      {listEntries.map(([k, v]) => {
        const arr = v as unknown[];
        if (arr.length === 0) return null;
        return (
          <div key={k}>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">{formatMetricKey(k)}</p>
            <div className="space-y-1 max-h-32 overflow-y-auto text-xs text-muted-foreground">
              {arr.slice(0, 5).map((item, i) => (
                <div key={i} className="bg-muted/30 rounded px-2 py-1">
                  {typeof item === "object" ? JSON.stringify(item) : String(item)}
                </div>
              ))}
              {arr.length > 5 && <p className="text-muted-foreground/60">+{arr.length - 5} more</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function FindingCard({
  finding,
  onDismiss,
}: {
  finding: InsightFinding;
  onDismiss?: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [showDismissConfirm, setShowDismissConfirm] = useState(false);
  const config = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.info;
  const Icon = config.icon;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="transition-colors hover:border-border">
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer py-3 px-4">
            <div className="flex items-center gap-3 w-full">
              <div className={`shrink-0 p-1.5 rounded-md ${config.bg}`}>
                <Icon className={`h-4 w-4 ${config.color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                    {CATEGORY_LABELS[finding.category] ?? finding.category}
                  </Badge>
                  <CardTitle className="text-sm font-medium truncate">
                    {finding.title}
                  </CardTitle>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Detected {formatRelativeTime(finding.first_detected_at)}
                  {finding.first_detected_at !== finding.last_detected_at && (
                    <> &middot; Last seen {formatRelativeTime(finding.last_detected_at)}</>
                  )}
                </p>
              </div>
              <div className="shrink-0">
                {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="pt-0 pb-4 px-4 space-y-3 border-t">
            <div className="pt-3">
              <p className="text-sm leading-relaxed">{finding.description}</p>
            </div>

            {finding.recommendation && (
              <div className="rounded-md bg-muted/50 p-3">
                <p className="text-xs font-semibold mb-1">Recommendation</p>
                <p className="text-sm text-muted-foreground">{finding.recommendation}</p>
              </div>
            )}

            {finding.metric_data && Object.keys(finding.metric_data).length > 0 && (
              <MetricDataView data={finding.metric_data} />
            )}

            {onDismiss && (
              <div className="flex justify-end pt-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowDismissConfirm(true);
                  }}
                >
                  <X className="h-3.5 w-3.5 mr-1" />
                  Dismiss
                </Button>
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>

      {onDismiss && (
        <ConfirmDialog
          open={showDismissConfirm}
          onOpenChange={setShowDismissConfirm}
          title="Dismiss finding?"
          description="This finding will be hidden from the active list. It can still be seen by filtering for dismissed findings."
          onConfirm={() => onDismiss(finding.id)}
          confirmLabel="Dismiss"
          variant="default"
        />
      )}
    </Collapsible>
  );
}
