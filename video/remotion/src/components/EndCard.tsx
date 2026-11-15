import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { clamp, enter } from "../anim";
import { AUTHORS, DISCLAIMER, REPO_URL } from "../config";
import { C } from "../tokens";
import { DoorGlyph } from "./DoorGlyph";

/** Night-kitchen end card: dark ink, cold blue light, the door, the three-line tagline. */
export const EndCard: React.FC<{ lines?: string[] }> = ({
  lines = ["AGENTS KNOCK.", "THE DOOR CHECKS.", "THE CHEF DECIDES."],
}) => {
  const frame = useCurrentFrame();
  const glow = interpolate(frame, [0, 40], [0.4, 1], clamp);
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(900px 700px at 22% 48%, rgba(60,140,235,${0.38 * glow}), transparent 70%), radial-gradient(1200px 500px at 100% 0%, rgba(142,192,255,0.10), transparent 70%)`,
        }}
      />
      <div style={{ position: "absolute", left: 190, top: 210, ...enter(frame, 0, 18, 30) }}>
        <div style={{ filter: `drop-shadow(0 0 ${40 * glow}px rgba(82,160,255,0.55))` }}>
          <DoorGlyph height={560} color="#2F82DB" />
        </div>
      </div>
      <div style={{ position: "absolute", left: 600, top: 168, width: 1260, color: C.paper }}>
        {lines.map((l, i) => (
          <div
            key={l}
            style={{
              fontSize: 116,
              fontWeight: 900,
              letterSpacing: "0.01em",
              lineHeight: 1.12,
              color: i === 1 ? "#8EC0FF" : C.paper,
              ...enter(frame, 14 + i * 16, 16, 34),
            }}
          >
            {l}
          </div>
        ))}
        <div style={{ marginTop: 56, fontSize: 40, fontWeight: 500, color: "#8EC0FF", letterSpacing: "0.02em", ...enter(frame, 70, 16, 16) }}>
          {REPO_URL}
        </div>
        <div style={{ marginTop: 18, fontSize: 32, fontWeight: 400, color: "#A9B2BC", ...enter(frame, 80, 16, 16) }}>{DISCLAIMER}</div>
        <div style={{ marginTop: 30, fontSize: 50, fontWeight: 700, color: C.paper, letterSpacing: "0.04em", ...enter(frame, 90, 16, 16) }}>
          {AUTHORS}
        </div>
      </div>
    </AbsoluteFill>
  );
};
