import React from "react";
import { C } from "../tokens";

export const Check: React.FC<{ size?: number; color?: string; sw?: number }> = ({ size = 40, color = C.green, sw = 6 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: "block" }}>
    <path d="M4 12.5l5 5L20 6.5" fill="none" stroke={color} strokeWidth={sw / 2.4} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Arrow: React.FC<{ size?: number; color?: string; length?: number }> = ({ size = 40, color = C.ink, length = 80 }) => (
  <svg width={length} height={size} viewBox={`0 0 ${length} ${size}`} style={{ display: "block", flex: "none" }}>
    <path
      d={`M2 ${size / 2}H${length - 6}M${length - 6 - size * 0.32} ${size / 2 - size * 0.32}L${length - 6} ${size / 2}L${length - 6 - size * 0.32} ${size / 2 + size * 0.32}`}
      fill="none"
      stroke={color}
      strokeWidth={5}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const Chevron: React.FC<{ height?: number; color?: string }> = ({ height = 60, color = C.mute }) => (
  <svg width={height * 0.5} height={height} viewBox="0 0 30 60" style={{ display: "block", flex: "none" }}>
    <path d="M6 6L24 30L6 54" fill="none" stroke={color} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Spinner: React.FC<{ size?: number; frame: number; color?: string }> = ({ size = 40, frame, color = C.blue }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: "block", transform: `rotate(${frame * 14}deg)` }}>
    <circle cx="12" cy="12" r="9" fill="none" stroke={C.line} strokeWidth="3" />
    <path d="M12 3a9 9 0 0 1 9 9" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" />
  </svg>
);
