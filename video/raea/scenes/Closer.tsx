import {
  AbsoluteFill,
  Easing,
  Video,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "raea";
import { css } from "../styles.gen";
import closerFootage from "../media/closer/candidate-a-8s.mp4";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const OUT = Easing.out(Easing.cubic);
const FPS = 30;
const FOOTAGE_FRAMES = 4 * FPS;
const DOOR_FRAMES = Math.round(0.8 * FPS);
const DEFAULT_DURATION = 8 * FPS;
const FONT_HEADING = "var(--brand-font-heading)";
const FONT_BODY = "var(--brand-font-body)";
const DOOR_MASK =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 100' shape-rendering='crispEdges'%3E%3Cpath fill-rule='evenodd' d='M0 100V30h2V22h2V16h2V12h4V8h4V6h4V4h4V2h4V0h8v2h4v2h4v2h4v2h4v4h4v4h2v6h2v8h2v70zM8 40h18v22H8zM34 40h18v22H34zM8 68h18v22H8zM34 68h18v22H34z'/%3E%3C/svg%3E\")";
const DOOR_SILHOUETTE_MASK =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 100' shape-rendering='crispEdges'%3E%3Cpath d='M0 100V30h2V22h2V16h2V12h4V8h4V6h4V4h4V2h4V0h8v2h4v2h4v2h4v2h4v4h4v4h2v6h2v8h2v70z'/%3E%3C/svg%3E\")";

export type CloserProps = {
  durationInFrames?: number;
  frameOffset?: number;
};

const TRACK_FRAMES = [0, 36, 72, 119];
const PHONE_TRACK = {
  x: [930, 925, 920, 902],
  y: [796, 798, 800, 806],
  width: [720, 736, 734, 704],
  height: [168, 172, 168, 160],
  rotation: [3.8, 3.4, 2.8, 2.2],
};

function track(frame: number, values: number[]) {
  return interpolate(frame, TRACK_FRAMES, values, CLAMP);
}

function DoorMark({ color = "var(--brand-lime)" }: { color?: string }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "block",
        width: "100%",
        height: "100%",
        background: color,
        maskImage: DOOR_MASK,
        WebkitMaskImage: DOOR_MASK,
        maskPosition: "center",
        WebkitMaskPosition: "center",
        maskRepeat: "no-repeat",
        WebkitMaskRepeat: "no-repeat",
        maskSize: "100% 100%",
        WebkitMaskSize: "100% 100%",
      }}
    />
  );
}

function OrderedSigned({ frame }: { frame: number }) {
  const opacity = interpolate(frame, [0, 8, 104, 119], [0, 1, 1, 0], CLAMP);
  const phoneX = track(frame, PHONE_TRACK.x);
  const phoneY = track(frame, PHONE_TRACK.y);
  const phoneWidth = track(frame, PHONE_TRACK.width);
  const phoneHeight = track(frame, PHONE_TRACK.height);
  const phoneRotation = track(frame, PHONE_TRACK.rotation);

  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        left: `${phoneX / 1920 * 100}%`,
        top: `${phoneY / 1080 * 100}%`,
        width: `${phoneWidth / 1920 * 100}%`,
        height: `${phoneHeight / 1080 * 100}%`,
        transform: `translate(-50%, -50%) rotate(${phoneRotation}deg)`,
        transformOrigin: "center center",
        overflow: "hidden",
        borderRadius: "10%",
        opacity,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
        padding: "3.5% 4.5%",
          boxSizing: "border-box",
          background: "linear-gradient(115deg, #0d2423 0%, #174f4b 58%, #247a69 100%)",
          color: "#f7fff9",
          fontFamily: FONT_BODY,
          boxShadow: "0 0 54px rgba(76, 195, 227, 0.78), inset 0 0 28px rgba(197, 225, 29, 0.22)",
          border: "1px solid rgba(160, 255, 220, 0.78)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "2.4%", fontSize: "clamp(18px, 1.35vw, 26px)", fontWeight: 800, letterSpacing: "0.04em", whiteSpace: "nowrap" }}>
          <span aria-hidden="true" style={{ display: "inline-flex", width: "1.2em", height: "1.2em", alignItems: "center", justifyContent: "center", borderRadius: "50%", background: "#c5e11d", color: "#0b2f3a" }}>✓</span>
          ORDER CONFIRMED
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "4%", marginTop: "3.2%", padding: "2.2% 3.2%", background: "rgba(7, 24, 24, 0.72)", borderRadius: 10, fontSize: "clamp(14px, 0.95vw, 19px)", lineHeight: 1.15 }}>
          <div>
            <div style={{ fontWeight: 750 }}>Valio · Monday kitchen order</div>
            <div style={{ marginTop: "3%", color: "#b8e7d0" }}>Signed · build 49730579fece</div>
          </div>
          <div style={{ color: "#c5e11d", fontWeight: 750, whiteSpace: "nowrap" }}>AUDIT SEALED</div>
        </div>
      </div>
    </div>
  );
}

function Footage({ frame }: { frame: number }) {
  const { width } = useVideoConfig();
  const u = width / 1920;
  return (
    <AbsoluteFill style={{ background: "var(--brand-ink)", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, transformOrigin: "48% 72%", transform: `translateY(-56px) scale(${interpolate(frame, [0, FOOTAGE_FRAMES - 1], [1, 1.08], { ...CLAMP, easing: OUT })})` }}>
        <Video
          src={closerFootage}
          startFrom={Math.round(1.2 * FPS)}
          endAt={Math.round(5.2 * FPS)}
          gainDb={-4}
          fadeIn={0.012}
          fadeOut={0.15}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", filter: "brightness(1.12) saturate(1.03) sepia(0.08)" }}
        />
        <div aria-hidden="true" style={{ position: "absolute", inset: 0, background: "rgba(255, 210, 150, 0.06)" }} />
        <OrderedSigned frame={frame} />
      </div>
      <div
        style={{
          position: "absolute",
          left: `${72 * u}px`,
          top: `${132 * u}px`,
          padding: `${10 * u}px ${15 * u}px`,
          border: "1px solid rgba(251, 250, 247, 0.72)",
          borderRadius: "var(--brand-radius)",
          background: "rgba(10, 10, 10, 0.56)",
          color: "var(--brand-background)",
          fontFamily: FONT_BODY,
          fontSize: `${22 * u}px`,
          lineHeight: 1,
        }}
      >
        Illustration · AI-generated
      </div>
    </AbsoluteFill>
  );
}

function DitherField({ phase }: { phase: number }) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "#000",
        backgroundImage: "conic-gradient(#00607a 25%, transparent 0 50%, #00607a 0 75%, transparent 0)",
        backgroundPosition: `${phase}px ${phase}px`,
        backgroundSize: "4px 4px",
      }}
    />
  );
}

function DoorClose({ frame }: { frame: number }) {
  const progress = interpolate(frame - FOOTAGE_FRAMES, [0, DOOR_FRAMES], [0, 1], { ...CLAMP, easing: OUT });
  const fade = interpolate(frame - FOOTAGE_FRAMES, [DOOR_FRAMES - 8, DOOR_FRAMES], [1, 0], CLAMP);
  const leafRotation = interpolate(progress, [0, 1], [-78, 0], CLAMP);
  const phase = Math.floor(frame * 0.9) % 6;
  return (
    <AbsoluteFill style={{ background: "var(--brand-ink)", opacity: fade, overflow: "hidden" }}>
      <div aria-hidden="true" style={{ position: "absolute", inset: 0, background: "var(--brand-accent)", opacity: 0.28 }} />
      <div style={{ position: "absolute", left: "50%", top: "50%", width: 402, height: 670, transform: "translate(-50%, -50%)", perspective: 1100 }}>
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            background: "var(--brand-background)",
            opacity: 0.92,
            maskImage: DOOR_SILHOUETTE_MASK,
            WebkitMaskImage: DOOR_SILHOUETTE_MASK,
            maskPosition: "center",
            WebkitMaskPosition: "center",
            maskRepeat: "no-repeat",
            WebkitMaskRepeat: "no-repeat",
            maskSize: "100% 100%",
            WebkitMaskSize: "100% 100%",
          }}
        />
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            transformOrigin: "left center",
            transform: `rotateY(${leafRotation}deg)`,
            maskImage: DOOR_MASK,
            WebkitMaskImage: DOOR_MASK,
            maskPosition: "center",
            WebkitMaskPosition: "center",
            maskRepeat: "no-repeat",
            WebkitMaskRepeat: "no-repeat",
            maskSize: "100% 100%",
            WebkitMaskSize: "100% 100%",
          }}
        >
          <DitherField phase={phase} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

function EndCard({ frame }: { frame: number }) {
  const local = frame - FOOTAGE_FRAMES - DOOR_FRAMES;
  const opacity = interpolate(local, [0, 12], [0, 1], CLAMP);
  const { width } = useVideoConfig();
  const u = width / 1920;
  return (
    <AbsoluteFill style={{ background: "#14171c", color: "var(--brand-background)", opacity, padding: `${96 * u}px ${84 * u}px` }}>
      <div style={{ position: "absolute", left: "50%", top: `${196 * u}px`, width: `${1320 * u}px`, transform: "translateX(-50%)", display: "flex", alignItems: "center", justifyContent: "center", gap: `${86 * u}px` }}>
        <div style={{ flex: "0 0 auto", width: `${230 * u}px`, height: `${382 * u}px`, filter: "drop-shadow(0 18px 20px rgba(0,0,0,0.28))" }}><DoorMark color="#4cc3e3" /></div>
        <div style={{ fontFamily: FONT_HEADING, fontSize: `${78 * u}px`, fontWeight: 700, letterSpacing: "-0.045em", lineHeight: 0.95 }}>
          <div>Agents knock.</div>
          <div>The door checks.</div>
          <div style={{ color: "#4cc3e3" }}>The chef decides.</div>
        </div>
      </div>
      <div style={{ position: "absolute", left: "50%", bottom: `${210 * u}px`, transform: "translateX(-50%)", width: `${1500 * u}px`, display: "flex", justifyContent: "space-between", gap: `${48 * u}px`, fontFamily: FONT_BODY, fontSize: `${22 * u}px`, lineHeight: 1.25, color: "#b9c0c8" }}>
        <div><div>{"github.com/omarjku/BengaliPharaohsJunction"}</div><div>{"valio-front-door.onrender.com"}</div></div>
        <div style={{ textAlign: "right" }}><div>{"Valio challenge mock · no real orders or payments"}</div><div>{"Omar Kassem & Fathia Fairuz Zoha"}</div></div>
      </div>
    </AbsoluteFill>
  );
}

export function Closer({ durationInFrames = DEFAULT_DURATION, frameOffset = 0 }: CloserProps) {
  const frame = Math.min(durationInFrames - 1, useCurrentFrame() + frameOffset);
  return (
    <AbsoluteFill>
      <style>{css}</style>
      {frame < FOOTAGE_FRAMES ? <Footage frame={frame} /> : null}
      {frame >= FOOTAGE_FRAMES && frame < FOOTAGE_FRAMES + DOOR_FRAMES ? <DoorClose frame={frame} /> : null}
      {frame >= FOOTAGE_FRAMES + DOOR_FRAMES ? <EndCard frame={frame} /> : null}
    </AbsoluteFill>
  );
}

export default Closer;
