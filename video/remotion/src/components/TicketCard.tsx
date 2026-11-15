import React from "react";
import { useCurrentFrame } from "remotion";
import { progress } from "../anim";
import { C } from "../tokens";
import { DoorGlyph } from "./DoorGlyph";

const Zig: React.FC<{ up?: boolean }> = ({ up }) => (
  <svg width="100%" height={14} style={{ display: "block" }}>
    <defs>
      <pattern id={up ? "zig-up" : "zig-down"} width="28" height="14" patternUnits="userSpaceOnUse">
        <path d={up ? "M0 14H28L14 0Z" : "M0 0H28L14 14Z"} fill={C.paper} />
      </pattern>
    </defs>
    <rect width="100%" height="14" fill={`url(#${up ? "zig-up" : "zig-down"})`} />
  </svg>
);

/** Thermal order-ticket card: torn zigzag edges, dashed rules, a soft shadow. */
export const TicketCard: React.FC<{
  title?: string;
  children?: React.ReactNode;
  width?: number;
  tilt?: number;
  at?: number;
  footer?: string;
  style?: React.CSSProperties;
}> = ({ title = "FRONT DOOR", children, width = 640, tilt = 0, at = 0, footer, style }) => {
  const frame = useCurrentFrame();
  const t = progress(frame, at, 16);
  return (
    <div
      style={{
        width,
        opacity: t,
        transform: `translateY(${(1 - t) * 40}px) rotate(${tilt}deg)`,
        filter: "drop-shadow(0 18px 26px rgba(28,31,35,0.18))",
        ...style,
      }}
    >
      <Zig up />
      <div style={{ background: C.paper, padding: "20px 40px 26px", color: C.ink }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            paddingBottom: 16,
            borderBottom: `3px dashed ${C.line}`,
            marginBottom: 18,
            color: C.mute,
            fontSize: 26,
            fontWeight: 700,
            letterSpacing: "0.14em",
          }}
        >
          <DoorGlyph height={34} color={C.blue} />
          <span>{title}</span>
        </div>
        {children}
        {footer && (
          <div
            style={{
              marginTop: 18,
              paddingTop: 14,
              borderTop: `3px dashed ${C.line}`,
              color: C.mute,
              fontSize: 24,
              fontWeight: 500,
              letterSpacing: "0.1em",
            }}
          >
            {footer}
          </div>
        )}
      </div>
      <Zig />
    </div>
  );
};
