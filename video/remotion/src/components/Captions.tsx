import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp } from "../anim";
import { TIMELINE } from "../timeline";
import { C } from "../tokens";
import { Beat } from "../types";

/** Split a caption into sentences, protecting "a.m." / "p.m.". */
export const splitSentences = (text: string): string[] =>
  text
    .replace(/\b([ap])\.m\./gi, "$1․m․")
    .split(/(?<=[.?!])\s+/)
    .map((s) => s.replace(/․/g, ".").trim())
    .filter(Boolean);

/** Burned-in captions: bottom, 44px, white on a 70% ink pill. One sentence at a time, timed by length. */
export const Captions: React.FC<{ beats?: Beat[] }> = ({ beats = TIMELINE }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const beat = beats.find((b) => t >= b.start && t < b.end);
  if (!beat || !beat.caption) return null;

  const parts = splitSentences(beat.caption);
  const lead = 0.2;
  const span = beat.end - beat.start - lead - 0.4;
  const total = parts.reduce((n, p) => n + p.length, 0);
  let acc = 0;
  const segs = parts.map((p) => {
    const s = beat.start + lead + (acc / total) * span;
    acc += p.length;
    return { text: p, start: s };
  });
  let idx = 0;
  segs.forEach((s, i) => {
    if (t >= s.start) idx = i;
  });
  const cur = segs[idx];
  const op = interpolate(t - cur.start, [0, 0.2], [0, 1], clamp);

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 54,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: 1560,
          padding: "14px 38px 16px",
          borderRadius: 24,
          background: "rgba(28,31,35,0.7)",
          border: "1px solid rgba(255,255,255,0.12)",
          color: C.paper,
          fontSize: 44,
          fontWeight: 500,
          lineHeight: 1.28,
          textAlign: "center",
          opacity: op,
        }}
      >
        {cur.text}
      </div>
    </div>
  );
};
