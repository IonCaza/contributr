import { useState, useCallback } from "react";

interface Run {
  id: string;
  status: string;
}

/**
 * Tracks an active run (insight run, SAST scan, etc.) with local state.
 * Auto-detects an already-running run on mount, and provides helpers
 * for triggering new runs and clearing state on completion.
 */
export function useActiveRunTracking(lastRun: Run | undefined) {
  const [activeRunId, setActiveRunId] = useState<string | null>(() => {
    if (lastRun && (lastRun.status === "running" || lastRun.status === "queued")) {
      return lastRun.id;
    }
    return null;
  });

  if (
    lastRun &&
    (lastRun.status === "running" || lastRun.status === "queued") &&
    !activeRunId
  ) {
    setActiveRunId(lastRun.id);
  }

  const startTracking = useCallback((runId: string) => {
    setActiveRunId(runId);
  }, []);

  const stopTracking = useCallback(() => {
    setActiveRunId(null);
  }, []);

  return { activeRunId, startTracking, stopTracking };
}
