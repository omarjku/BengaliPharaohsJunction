import { CSSProperties } from "react";
import { Easing, interpolate } from "remotion";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const easeOut = Easing.out(Easing.cubic);

/** 0..1 progress between frame `at` and `at + dur`, eased. */
export const progress = (frame: number, at: number, dur = 14): number =>
  interpolate(frame, [at, at + dur], [0, 1], { ...clamp, easing: easeOut });

/** Fade + rise entrance style. */
export const enter = (frame: number, at = 0, dur = 14, dist = 28): CSSProperties => {
  const t = progress(frame, at, dur);
  return { opacity: t, transform: `translateY(${(1 - t) * dist}px)` };
};
