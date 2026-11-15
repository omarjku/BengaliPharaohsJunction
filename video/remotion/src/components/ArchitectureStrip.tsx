import React from "react";
import { useCurrentFrame } from "remotion";
import { progress } from "../anim";
import { C } from "../tokens";
import { DoorGlyph } from "./DoorGlyph";
import { Chevron } from "./Icons";

export const ARCH_STEPS = ["AGENT PROPOSAL", "FRONT DOOR CHECKS", "CHEF APPROVAL", "SIGNED ORDER"];

/** AGENT PROPOSAL > FRONT DOOR CHECKS > CHEF APPROVAL > SIGNED ORDER, revealed left to right. */
export const ArchitectureStrip: React.FC<{ steps?: string[]; at?: number; width?: number; interval?: number }> = ({
  steps = ARCH_STEPS,
  at = 0,
  width = 1700,
  interval = 20,
}) => {
  const frame = useCurrentFrame();
  const gap = 12;
  const chevW = 30;
  const boxW = (width - (steps.length - 1) * (chevW + gap * 2)) / steps.length;
  const styleFor = (i: number) => {
    if (i === 1) return { bg: C.blue, fg: C.paper, border: C.blue };
    if (i === 2) return { bg: C.amberBg, fg: C.amber, border: C.amber };
    if (i === 3) return { bg: C.greenBg, fg: C.green, border: C.green };
    return { bg: C.paper, fg: C.ink, border: C.line };
  };
  return (
    <div style={{ display: "flex", alignItems: "center", width, gap }}>
      {steps.map((s, i) => {
        const p = progress(frame, at + i * interval, 14);
        const st = styleFor(i);
        return (
          <React.Fragment key={s}>
            {i > 0 && (
              <div style={{ opacity: p, display: "flex" }}>
                <Chevron height={64} color={C.mute} />
              </div>
            )}
            <div
              style={{
                width: boxW,
                height: 190,
                boxSizing: "border-box",
                background: st.bg,
                color: st.fg,
                border: `4px solid ${st.border}`,
                borderRadius: 22,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                textAlign: "center",
                fontSize: 38,
                fontWeight: 900,
                letterSpacing: "0.05em",
                lineHeight: 1.12,
                padding: "0 16px",
                opacity: p,
                transform: `translateY(${(1 - p) * 24}px)`,
                boxShadow: "0 10px 22px rgba(28,31,35,0.10)",
              }}
            >
              {i === 1 && <DoorGlyph height={54} color={C.paper} />}
              {s}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
};
