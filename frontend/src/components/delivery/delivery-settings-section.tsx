"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Plus, X } from "lucide-react";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  useDeliverySettings,
  useUpdateDeliverySettings,
  useDeliverySettingsAvailableStates,
  useDeliverySettingsAvailableCustomFields,
} from "@/hooks/use-delivery";
import type { ProjectDeliverySettings, ProjectDeliverySettingsUpdate } from "@/lib/types";

type StateKey = keyof Pick<
  ProjectDeliverySettings,
  "cycle_time_start_states"
  | "cycle_time_end_states"
  | "review_states"
  | "testing_states"
  | "ready_states"
>;

const STATE_FIELDS: Array<{ key: StateKey; label: string; description: string }> = [
  {
    key: "cycle_time_start_states",
    label: "Cycle time – start states",
    description:
      "States that mark the START of cycle time (e.g. Active). Transition into any of these starts the timer.",
  },
  {
    key: "cycle_time_end_states",
    label: "Cycle time – end states",
    description:
      "States that mark the END of cycle time (e.g. Closed). Pick Closed to exclude review/testing time that ends at Resolved.",
  },
  {
    key: "review_states",
    label: "Review states",
    description: "States representing the code-review phase.",
  },
  {
    key: "testing_states",
    label: "Testing states",
    description: "States representing the testing/QA phase.",
  },
  {
    key: "ready_states",
    label: "Ready states",
    description: "Backlog states counted as “ready to pick up” when measuring planning horizon.",
  },
];

const HEALTH_THRESHOLD_KEYS: Array<{
  key: string;
  label: string;
  description: string;
  suffix?: string;
  min: number;
  max: number;
}> = [
  { key: "unestimated_pct_warn", label: "Unestimated – warn", description: "% of active items missing story points before warning.", suffix: "%", min: 0, max: 100 },
  { key: "unestimated_pct_crit", label: "Unestimated – critical", description: "% of active items missing story points before critical.", suffix: "%", min: 0, max: 100 },
  { key: "unassigned_pct_warn", label: "Unassigned – warn", description: "% of active items with no assignee before warning.", suffix: "%", min: 0, max: 100 },
  { key: "unassigned_pct_crit", label: "Unassigned – critical", description: "% of active items with no assignee before critical.", suffix: "%", min: 0, max: 100 },
  { key: "stale_days", label: "Stale threshold", description: "Days without an update for a backlog item to count as stale.", suffix: "d", min: 1, max: 365 },
  { key: "stale_pct_warn", label: "Stale – warn", description: "% of backlog items considered stale before warning.", suffix: "%", min: 0, max: 100 },
  { key: "stale_pct_crit", label: "Stale – critical", description: "% of backlog items considered stale before critical.", suffix: "%", min: 0, max: 100 },
  { key: "planning_sprints_min", label: "Planning horizon (min sprints)", description: "Ready-state backlog must cover at least this many sprints.", suffix: "sp", min: 1, max: 10 },
];

const SENTINEL_NO_TSHIRT = "__none__";

function StateTagPicker({
  value,
  available,
  onChange,
}: {
  value: string[];
  available: string[];
  onChange: (next: string[]) => void;
}) {
  const [addOpen, setAddOpen] = useState(false);
  const [customInput, setCustomInput] = useState("");

  const addable = useMemo(
    () => available.filter((a) => !value.includes(a)),
    [available, value],
  );

  function add(v: string) {
    const trimmed = v.trim();
    if (!trimmed || value.includes(trimmed)) return;
    onChange([...value, trimmed]);
  }

  function remove(v: string) {
    onChange(value.filter((x) => x !== v));
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {value.length === 0 && (
          <span className="text-xs text-muted-foreground italic">None selected</span>
        )}
        {value.map((s) => (
          <Badge key={s} variant="secondary" className="pl-2 pr-1 gap-1">
            <span className="text-xs">{s}</span>
            <button
              type="button"
              onClick={() => remove(s)}
              className="rounded hover:bg-muted-foreground/20"
              aria-label={`Remove ${s}`}
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-6 px-2 text-xs"
          onClick={() => setAddOpen((o) => !o)}
        >
          <Plus className="h-3 w-3 mr-1" /> Add
        </Button>
      </div>
      {addOpen && (
        <div className="rounded-md border bg-muted/30 p-2 space-y-2">
          {addable.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {addable.map((a) => (
                <button
                  key={a}
                  type="button"
                  className="text-[11px] rounded px-1.5 py-0.5 bg-background border hover:bg-accent"
                  onClick={() => add(a)}
                >
                  + {a}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-1">
            <Input
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              placeholder="Custom state name…"
              className="h-7 text-xs"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  add(customInput);
                  setCustomInput("");
                }
              }}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => {
                add(customInput);
                setCustomInput("");
              }}
              disabled={!customInput.trim()}
            >
              Add
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function DeliverySettingsSection({ projectId }: { projectId: string }) {
  const { data: settings, isLoading } = useDeliverySettings(projectId);
  const { data: statesData } = useDeliverySettingsAvailableStates(projectId);
  const { data: fieldsData } = useDeliverySettingsAvailableCustomFields(projectId);
  const update = useUpdateDeliverySettings(projectId);

  const [form, setForm] = useState<ProjectDeliverySettingsUpdate>({});
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (settings) {
      setForm({
        cycle_time_start_states: settings.cycle_time_start_states,
        cycle_time_end_states: settings.cycle_time_end_states,
        review_states: settings.review_states,
        testing_states: settings.testing_states,
        ready_states: settings.ready_states,
        tshirt_custom_field: settings.tshirt_custom_field,
        backlog_health_thresholds: settings.backlog_health_thresholds,
        long_running_threshold_days: settings.long_running_threshold_days,
        rolling_capacity_sprints: settings.rolling_capacity_sprints,
      });
      setDirty(false);
    }
  }, [settings]);

  const availableStates = statesData?.states ?? [];
  const availableFields = fieldsData?.keys ?? [];

  function setStateField(key: StateKey, value: string[]) {
    setForm((f) => ({ ...f, [key]: value }));
    setDirty(true);
  }

  function setThreshold(key: string, value: number) {
    setForm((f) => ({
      ...f,
      backlog_health_thresholds: {
        ...(f.backlog_health_thresholds ?? {}),
        [key]: value,
      },
    }));
    setDirty(true);
  }

  function handleSave() {
    update.mutate(form, { onSuccess: () => setDirty(false) });
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading delivery analytics settings…
        </CardContent>
      </Card>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Delivery analytics</h2>
          <p className="text-sm text-muted-foreground">
            Tune how cycle time, backlog health, and long-running stories are measured for this project.
          </p>
        </div>
        {update.isPending && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Saving…
          </div>
        )}
        {!update.isPending && update.isSuccess && !dirty && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Check className="h-3.5 w-3.5" /> Saved
          </div>
        )}
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">State mappings</CardTitle>
          <CardDescription className="text-xs">
            Pick which work-item states belong to each phase. Values come from states observed on this project; you
            can also add custom ones.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {STATE_FIELDS.map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label className="text-sm">{f.label}</Label>
              <p className="text-[11px] text-muted-foreground">{f.description}</p>
              <StateTagPicker
                value={(form[f.key] as string[]) ?? []}
                available={availableStates}
                onChange={(v) => setStateField(f.key, v)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">T-shirt sizing</CardTitle>
          <CardDescription className="text-xs">
            If your team captures a t-shirt size as a custom field, pick the key so feature rollups can group by
            size. Leave unset if you size only with story points.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Select
            value={form.tshirt_custom_field ?? SENTINEL_NO_TSHIRT}
            onValueChange={(v) => {
              setForm((f) => ({
                ...f,
                tshirt_custom_field: v === SENTINEL_NO_TSHIRT ? null : v,
              }));
              setDirty(true);
            }}
          >
            <SelectTrigger className="w-72">
              <SelectValue placeholder="Select a custom-field key" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SENTINEL_NO_TSHIRT}>— No t-shirt field —</SelectItem>
              {availableFields.map((k) => (
                <SelectItem key={k} value={k}>{k}</SelectItem>
              ))}
              {form.tshirt_custom_field && !availableFields.includes(form.tshirt_custom_field) && (
                <SelectItem value={form.tshirt_custom_field}>
                  {form.tshirt_custom_field} (not observed yet)
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Backlog health thresholds</CardTitle>
          <CardDescription className="text-xs">
            Traffic-light cut-offs for the trusted-backlog scorecard and related insights.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {HEALTH_THRESHOLD_KEYS.map((t) => (
            <div key={t.key} className="space-y-1">
              <Label className="text-xs">{t.label}</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={t.min}
                  max={t.max}
                  value={(form.backlog_health_thresholds?.[t.key] as number | undefined) ?? 0}
                  onChange={(e) => setThreshold(t.key, Number(e.target.value))}
                  className="h-8 w-28"
                />
                {t.suffix && (
                  <span className="text-xs text-muted-foreground">{t.suffix}</span>
                )}
                <span className="text-[11px] text-muted-foreground flex-1">{t.description}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Detection windows</CardTitle>
          <CardDescription className="text-xs">
            How long stories can run and how much history to use for team capacity.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="long-running-days" className="text-sm">Long-running threshold (days)</Label>
            <p className="text-[11px] text-muted-foreground">
              Items active longer than this are flagged as long-running. Default 14.
            </p>
            <Input
              id="long-running-days"
              type="number"
              min={1}
              max={365}
              value={form.long_running_threshold_days ?? 14}
              onChange={(e) => {
                setForm((f) => ({ ...f, long_running_threshold_days: Number(e.target.value) }));
                setDirty(true);
              }}
              className="h-8 w-32"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="rolling-capacity-sprints" className="text-sm">Rolling capacity (sprints)</Label>
            <p className="text-[11px] text-muted-foreground">
              How many recent sprints to average when computing team capacity. Default 3.
            </p>
            <Input
              id="rolling-capacity-sprints"
              type="number"
              min={1}
              max={20}
              value={form.rolling_capacity_sprints ?? 3}
              onChange={(e) => {
                setForm((f) => ({ ...f, rolling_capacity_sprints: Number(e.target.value) }));
                setDirty(true);
              }}
              className="h-8 w-32"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={!dirty || update.isPending}
          onClick={() => {
            if (settings) {
              setForm({
                cycle_time_start_states: settings.cycle_time_start_states,
                cycle_time_end_states: settings.cycle_time_end_states,
                review_states: settings.review_states,
                testing_states: settings.testing_states,
                ready_states: settings.ready_states,
                tshirt_custom_field: settings.tshirt_custom_field,
                backlog_health_thresholds: settings.backlog_health_thresholds,
                long_running_threshold_days: settings.long_running_threshold_days,
                rolling_capacity_sprints: settings.rolling_capacity_sprints,
              });
              setDirty(false);
            }
          }}
        >
          Discard
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!dirty || update.isPending}
        >
          {update.isPending ? (
            <><Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />Saving…</>
          ) : (
            "Save delivery settings"
          )}
        </Button>
      </div>
    </section>
  );
}
