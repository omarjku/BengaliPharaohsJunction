import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig } from "remotion";
import { clamp } from "./anim";
import { Captions } from "./components/Captions";
import { HAS_MUSIC, HAS_VO } from "./config";
import { Scene } from "./scenes";
import { TIMELINE } from "./timeline";
import { C, FONT } from "./tokens";

export type FrontDoorProps = { hasVo: boolean; hasMusic: boolean };

export const frontDoorDefaults: FrontDoorProps = { hasVo: HAS_VO, hasMusic: HAS_MUSIC };

export const FrontDoor: React.FC<FrontDoorProps> = ({ hasVo, hasMusic }) => {
  const { fps, durationInFrames } = useVideoConfig();
  // Music is ducked well under the voice when a voice track exists.
  const base = hasVo ? 0.12 : 0.4;
  return (
    <AbsoluteFill style={{ background: C.ink, fontFamily: FONT, color: C.ink }}>
      {TIMELINE.map((b) => (
        <Sequence
          key={b.id}
          name={b.id}
          from={Math.round(b.start * fps)}
          durationInFrames={Math.round((b.end - b.start) * fps)}
        >
          <Scene beat={b} />
        </Sequence>
      ))}
      <Captions />
      {hasVo && <Audio src={staticFile("vo.wav")} />}
      {hasMusic && (
        <Audio
          src={staticFile("music.mp3")}
          loop
          volume={(f) => base * interpolate(f, [0, fps, durationInFrames - 2 * fps, durationInFrames], [0, 1, 1, 0], clamp)}
        />
      )}
    </AbsoluteFill>
  );
};
