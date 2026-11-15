import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { clamp, progress } from "../anim";
import { C, TONES } from "../tokens";
import { EvidenceItem } from "../types";

/** Evidence stat cards that reveal one at a time. `interval` = frames between reveals. */
export const EvidenceCards: React.FC<{
  items: EvidenceItem[];
  note?: string;
  at?: number;
  interval?: number;
  width?: number;
}> = ({ items, note, at = 0, interval = 60, width = 1700 }) => {
  const frame = useCurrentFrame();
  const gap = 36;
  const cardW = (width - gap * (items.length - 1)) / items.length;
  return (
    <div style={{ width }}>
      <div style={{ display: "flex", gap }}>
        {items.map((it, i) => {
          const start = at + i * interval;
          const p = progress(frame, start, 16);
          const tone = TONES[it.tone ?? "blue"];
          // brief emphasis ring while it is the newest card
          const fresh = interpolate(frame, [start, start + 10, start + interval], [0, 1, 0], clamp);
          return (
            <div
              key={it.label}
              style={{
                width: cardW,
                boxSizing: "border-box",
                background: C.paper,
                borderRadius: 24,
                border: `4px solid ${fresh > 0.5 ? tone.fg : C.line}`,
                borderTop: `16px solid ${tone.fg}`,
                padding: "26px 34px 34px",
                opacity: p,
                transform: `translateY(${(1 - p) * 50}px) scale(${0.96 + 0.04 * p})`,
                boxShadow: "0 16px 30px rgba(28,31,35,0.12)",
                display: "flex",
                flexDirection: "column",
                minHeight: 380,
              }}
            >
              <div style={{ display: "flex", alignItems: "baseline", gap: 18, color: tone.fg, fontWeight: 900, lineHeight: 1 }}>
                <span style={{ fontSize: 190, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{it.big}</span>
                {it.suffix && <span style={{ fontSize: 76 }}>{it.suffix}</span>}
              </div>
              <div style={{ marginTop: 22, fontSize: 40, fontWeight: 700, letterSpacing: "0.05em", lineHeight: 1.2, color: C.ink }}>
                {it.label}
              </div>
            </div>
          );
        })}
      </div>
      {note && (
        <div
          style={{
            marginTop: 34,
            fontSize: 32,
            fontWeight: 500,
            color: C.mute,
            fontStyle: "italic",
            opacity: progress(frame, at + items.length * interval, 16),
          }}
        >
          {note}
        </div>
      )}
    </div>
  );
};
