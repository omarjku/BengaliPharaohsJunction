import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp } from "../anim";
import { TONES, Tone } from "../tokens";

/**
 * An ink stamp that "lands": scale from large to 1 and a slight rotate, on a spring.
 * `at` is the frame (inside the current Sequence) where it lands; `exitAt` fades it out.
 */
export const Stamp: React.FC<{
  label: string;
  tone?: Tone;
  at?: number;
  exitAt?: number;
  rotate?: number;
  size?: number;
  style?: React.CSSProperties;
}> = ({ label, tone = "amber", at = 0, exitAt, rotate = -6, size = 64, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fg, bg } = TONES[tone];
  const t = frame - at;
  const s = spring({ frame: t, fps, config: { damping: 10, stiffness: 260, mass: 0.6 } });
  const scale = interpolate(s, [0, 1], [2.8, 1]);
  const rot = interpolate(s, [0, 1], [rotate - 18, rotate]);
  let opacity = interpolate(t, [0, 3], [0, 1], clamp);
  if (exitAt !== undefined) opacity *= interpolate(frame, [exitAt, exitAt + 8], [1, 0], clamp);
  const ring = interpolate(t, [2, 22], [0, 1], clamp);
  const bw = Math.max(4, size * 0.11);

  return (
    <div
      style={{
        position: "relative",
        display: "inline-block",
        opacity,
        transform: `rotate(${rot}deg) scale(${scale})`,
        ...style,
      }}
    >
      <div
        style={{
          border: `${bw}px solid ${fg}`,
          borderRadius: size * 0.22,
          padding: `${size * 0.16}px ${size * 0.38}px`,
          background: `${bg}F2`,
          color: fg,
          fontWeight: 900,
          fontSize: size,
          letterSpacing: "0.06em",
          lineHeight: 1,
          whiteSpace: "nowrap",
          boxShadow: `inset 0 0 0 ${size * 0.04}px ${bg}, inset 0 0 0 ${size * 0.07}px ${fg}`,
        }}
      >
        {label}
      </div>
      {/* impact ring */}
      <div
        style={{
          position: "absolute",
          inset: -ring * 36,
          border: `${Math.max(3, size * 0.06)}px solid ${fg}`,
          borderRadius: size * 0.22 + ring * 36,
          opacity: (1 - ring) * 0.45 * (t > 2 ? 1 : 0),
        }}
      />
    </div>
  );
};
