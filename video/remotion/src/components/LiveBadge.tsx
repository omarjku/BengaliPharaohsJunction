import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C } from "../tokens";

/** "LIVE · ONE TAKE" badge with a pulsing dot. Pass x4 for an extra "x4" (sped-up) badge. */
export const LiveBadge: React.FC<{ x4?: boolean; style?: React.CSSProperties }> = ({ x4, style }) => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame / 6), [-1, 1], [0.45, 1]);
  const pill: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 14,
    background: C.ink,
    color: C.paper,
    fontSize: 30,
    fontWeight: 900,
    letterSpacing: "0.12em",
    padding: "10px 24px",
    borderRadius: 999,
  };
  return (
    <div style={{ display: "flex", gap: 12, ...style }}>
      <div style={pill}>
        <span style={{ width: 18, height: 18, borderRadius: 9, background: "#FF5A4D", opacity: pulse }} />
        LIVE · ONE TAKE
      </div>
      {x4 && <div style={{ ...pill, background: C.blue }}>x4</div>}
    </div>
  );
};
