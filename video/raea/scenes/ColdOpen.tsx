import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  Video,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "raea";
import { css } from "../styles.gen";
import { DoorGlyph } from "./DoorTransition";
import candidateA from "../media/coldopen/candidate-a.mp4";
import notificationChime from "../media/coldopen/notification-chime.wav";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const OUT = Easing.out(Easing.cubic);
const DEFAULT_DURATION = 210;
const NOTIFY_FRAME = 45;
const FONT_FACES = `
@font-face { font-family: 'Pixelify Sans'; font-style: normal; font-weight: 400; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TTp0H1Y.ttf') format('truetype'); }
@font-face { font-family: 'Pixelify Sans'; font-style: normal; font-weight: 500; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TTb0H1Y.ttf') format('truetype'); }
@font-face { font-family: 'Pixelify Sans'; font-style: normal; font-weight: 600; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TQ3131Y.ttf') format('truetype'); }
`;

export type ColdOpenProps = {
  durationInFrames?: number;
  frameOffset?: number;
  progress?: number;
};

const TRACK_FRAMES = [0, 34, 68, 102, 136, 170, 204, 239];
const TRACK = {
  x: [972, 972, 970, 970, 968, 967, 966, 965],
  y: [617, 616, 613, 611, 610, 609, 608, 608],
  width: [220, 224, 231, 240, 252, 266, 283, 300],
  height: [438, 442, 451, 462, 477, 494, 515, 536],
  rotation: [4.2, 4.1, 3.9, 3.8, 3.5, 3.2, 2.9, 2.7],
};

function trackedValue(frame: number, values: number[]) {
  return interpolate(frame, TRACK_FRAMES, values, CLAMP);
}

function NotificationBanner({ frame }: { frame: number }) {
  const inFrame = frame - NOTIFY_FRAME;
  const opacity = interpolate(inFrame, [0, 5], [0, 1], CLAMP);
  const y = interpolate(inFrame, [0, 8], [26, 0], { ...CLAMP, easing: OUT });
  const scale = interpolate(inFrame, [0, 5, 9, 15], [0.9, 1.04, 0.985, 1], CLAMP);
  return (
    <div
      style={{
        position: "absolute",
        left: "4%",
        top: "13%",
        width: "92%",
        minHeight: "40%",
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        boxSizing: "border-box",
        padding: "14px 15px",
        border: "1px solid rgba(255,255,255,0.15)",
        borderRadius: 18,
        background: "rgba(28, 31, 35, 0.92)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.24)",
        backdropFilter: "blur(12px)",
        opacity,
        transform: `translateY(${y}px) scale(${scale})`,
        transformOrigin: "center top",
      }}
    >
      <span
        style={{
          flex: "0 0 40px",
          width: 40,
          height: 40,
          display: "block",
          padding: 6,
          boxSizing: "border-box",
          borderRadius: 8,
          background: "#081218",
          border: "1px solid rgba(76,195,227,0.48)",
        }}
      >
        <DoorGlyph />
      </span>
        <span style={{ display: "block", minWidth: 0, color: "#f2f2f2", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", lineHeight: 1.08 }}>
        <span style={{ display: "block", fontSize: 16, fontWeight: 700, lineHeight: 1.05 }}>Reminders</span>
        <span style={{ display: "block", marginTop: 4, fontSize: 15.5, fontWeight: 650, lineHeight: 1.08, whiteSpace: "normal" }}>Monday order · 500 guests</span>
        <span style={{ display: "block", marginTop: 5, color: "#c9ccd1", fontSize: 14.5, lineHeight: 1.15, whiteSpace: "normal" }}>Valio cut-off at 10:00. Order still not placed.</span>
      </span>
    </div>
  );
}

/**
 * Over-shoulder phone opener. The notification is composited on a measured,
 * keyframed phone plane rather than floating over the footage.
 */
export function ColdOpen({ durationInFrames = DEFAULT_DURATION, frameOffset = 0, progress }: ColdOpenProps) {
  const localFrame = useCurrentFrame();
  const { width } = useVideoConfig();
  const frame = progress == null ? localFrame + frameOffset : progress * durationInFrames;
  const trackFrame = interpolate(frame, [0, durationInFrames - 1], [0, 239], CLAMP);
  const phoneX = trackedValue(trackFrame, TRACK.x);
  const phoneY = trackedValue(trackFrame, TRACK.y);
  const phoneWidth = trackedValue(trackFrame, TRACK.width);
  const phoneHeight = trackedValue(trackFrame, TRACK.height);
  const phoneRotation = trackedValue(trackFrame, TRACK.rotation);
  const punchStart = Math.round(2.4 * 30);
  const punchEnd = punchStart + 30;
  const punch = interpolate(frame, [punchStart, punchEnd], [1, 2.2], { ...CLAMP, easing: Easing.inOut(Easing.cubic) });
  const u = width / 1920;

  return (
    <AbsoluteFill style={{ background: "#0a0a0a", overflow: "hidden" }}>
      <style>{css + FONT_FACES}</style>
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", transformOrigin: `${phoneX / 1920 * 100}% ${phoneY / 1080 * 100}%`, transform: `scale(${punch})` }}>
        <Video
          src={candidateA}
          endAt={durationInFrames}
          gainDb={-4}
          fadeIn={0.012}
          fadeOut={0.15}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", filter: "brightness(1.08) saturate(0.96)" }}
        />
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            left: `${phoneX / 1920 * 100}%`,
            top: `${phoneY / 1080 * 100}%`,
            width: `${phoneWidth * u}px`,
            height: `${phoneHeight * u}px`,
            transform: `translate(-50%, -50%) rotate(${phoneRotation}deg)`,
            transformOrigin: "center center",
            overflow: "hidden",
            borderRadius: "11%",
          }}
        >
          {frame >= NOTIFY_FRAME ? <NotificationBanner frame={frame} /> : null}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: `${72 * u}px`,
          top: `${140 * u}px`,
          padding: `${10 * u}px ${15 * u}px`,
          border: "1px solid rgba(251,250,247,0.72)",
          borderRadius: "var(--brand-radius)",
          background: "rgba(10, 10, 10, 0.56)",
          color: "var(--brand-background)",
          fontFamily: "'Pixelify Sans', ui-monospace, monospace",
          fontSize: `${22 * u}px`,
          lineHeight: 1,
          letterSpacing: "0.01em",
        }}
      >
        Illustration · AI-generated
      </div>

      <Sequence from={NOTIFY_FRAME} durationInFrames={Math.min(30, Math.max(1, durationInFrames - NOTIFY_FRAME))} layout="none" name="notification-chime">
        <Audio src={notificationChime} gainDb={-16} fadeIn={0.01} fadeOut={0.45} />
      </Sequence>
    </AbsoluteFill>
  );
}
