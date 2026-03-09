import type { CSSProperties } from "react";

export const ANIM_CARD = "animate-in fade-in slide-in-from-bottom-2 duration-400 fill-mode-both";

export function stagger(i: number): CSSProperties {
  return { animationDelay: `${100 + i * 75}ms` };
}
