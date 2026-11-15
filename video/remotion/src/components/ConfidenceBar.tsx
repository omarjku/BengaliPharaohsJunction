import React from "react";
import { useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { C } from "../tokens";
import { Score } from "../types";

/**
 * Confidence scores against a dashed threshold line ("ASK BELOW 0.70").
 * `big` = full-width hero version; `zoneLeft`/`zoneRight` label the two sides of the line.
 */
export const ConfidenceBar: React.FC<{
  scores: Score[];
  threshold: number;
  width?: number;
  at?: number;
  big?: boolean;
  zoneLeft?: string;
  zoneRight?: string;
}> = ({ scores, threshold, width = 1000, at = 0, big = false, zoneLeft, zoneRight }) => {
  const frame = useCurrentFrame();
  const trackH = big ? 76 : 52;
  const fs = big ? 44 : 34;
  const lineX = threshold * width;
  const label = `ASK BELOW ${threshold.toFixed(2)}`;

  return (
    <div style={{ position: "relative", width, paddingTop: big ? 84 : 72, ...enter(frame, at, 14, 20) }}>
      {/* threshold line + label */}
      <div
        style={{
          position: "absolute",
          left: lineX,
          top: big ? 46 : 38,
          bottom: zoneLeft ? 74 : 0,
          width: 0,
          borderLeft: `5px dashed ${C.ink}`,
          zIndex: 3,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: lineX,
          top: 0,
          transform: "translateX(-50%)",
          background: C.ink,
          color: C.paper,
          fontWeight: 900,
          fontSize: big ? 34 : 28,
          letterSpacing: "0.1em",
          padding: big ? "8px 22px" : "6px 18px",
          borderRadius: 10,
          whiteSpace: "nowrap",
          zIndex: 4,
        }}
      >
        {label}
      </div>

      {scores.map((s, i) => {
        const p = progress(frame, at + 10 + i * 12, 34);
        const color = s.out ? C.red : C.green;
        const bg = s.out ? C.redBg : C.greenBg;
        return (
          <div key={s.label} style={{ marginBottom: big ? 40 : 30 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                fontSize: fs,
                fontWeight: 700,
                letterSpacing: "0.04em",
                marginBottom: 10,
                color: C.ink,
              }}
            >
              <span>{s.label}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 16 }}>
                {s.out && (
                  <span
                    style={{
                      background: bg,
                      color,
                      border: `3px solid ${color}`,
                      borderRadius: 10,
                      fontSize: fs * 0.7,
                      fontWeight: 900,
                      padding: "2px 14px",
                      letterSpacing: "0.1em",
                      opacity: progress(frame, at + 36 + i * 12, 8),
                    }}
                  >
                    OUT
                  </span>
                )}
                <span style={{ color, fontWeight: 900, fontVariantNumeric: "tabular-nums" }}>
                  {(s.value * p).toFixed(3)}
                </span>
              </span>
            </div>
            <div style={{ height: trackH, borderRadius: 14, background: "#E1E5EA", overflow: "hidden", position: "relative" }}>
              <div style={{ width: `${s.value * p * 100}%`, height: "100%", background: color, borderRadius: 14 }} />
            </div>
          </div>
        );
      })}

      {zoneLeft && zoneRight && (
        <div style={{ display: "flex", height: 60, fontSize: 28, fontWeight: 900, letterSpacing: "0.1em", marginTop: 6 }}>
          <div
            style={{
              width: lineX,
              boxSizing: "border-box",
              background: C.amberBg,
              color: C.amber,
              border: `3px solid ${C.amber}`,
              borderRadius: "12px 0 0 12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {zoneLeft}
          </div>
          <div
            style={{
              flex: 1,
              boxSizing: "border-box",
              background: C.wash,
              color: C.mute,
              border: `3px solid ${C.line}`,
              borderLeft: "none",
              borderRadius: "0 12px 12px 0",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {zoneRight}
          </div>
        </div>
      )}
    </div>
  );
};
