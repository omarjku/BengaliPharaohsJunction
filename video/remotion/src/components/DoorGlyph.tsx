import React from "react";
import { C } from "../tokens";

export const DOOR_PATH =
  "M0 100V30h2V22h2V16h2V12h4V8h4V6h4V4h4V2h4V0h8v2h4v2h4v2h4v2h4v4h4v4h2v6h2v8h2v70zM8 40h18v22H8zM34 40h18v22H34zM8 68h18v22H8zM34 68h18v22H34z";

/** The Front Door glyph. `height` in px, width follows the 60x100 viewBox. */
export const DoorGlyph: React.FC<{ height?: number; color?: string; style?: React.CSSProperties }> = ({
  height = 100,
  color = C.blue,
  style,
}) => (
  <svg viewBox="0 0 60 100" width={(height * 60) / 100} height={height} style={{ display: "block", ...style }}>
    <path fillRule="evenodd" fill={color} d={DOOR_PATH} />
  </svg>
);
