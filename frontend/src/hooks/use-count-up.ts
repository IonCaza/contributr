"use client";

import { useState, useEffect, useRef } from "react";

export function useCountUp(target: number, duration = 600): number {
  const [value, setValue] = useState(0);
  const prevTarget = useRef(target);
  const rafId = useRef<number>(undefined);

  useEffect(() => {
    if (target === prevTarget.current && value !== 0) return;
    prevTarget.current = target;

    if (target === 0) {
      setValue(0);
      return;
    }

    const decimals = (target.toString().split(".")[1] || "").length;
    const factor = Math.pow(10, decimals);
    const start = performance.now();
    const from = 0;

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round((from + (target - from) * eased) * factor) / factor);
      if (progress < 1) {
        rafId.current = requestAnimationFrame(tick);
      }
    }

    rafId.current = requestAnimationFrame(tick);
    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [target, duration]);

  return value;
}
