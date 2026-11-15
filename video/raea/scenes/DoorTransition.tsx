import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "raea";
import { css } from "../styles.gen";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const OUT = Easing.out(Easing.cubic);
const DOOR_MASK =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 100' shape-rendering='crispEdges'%3E%3Cpath fill-rule='evenodd' d='M0 100V30h2V22h2V16h2V12h4V8h4V6h4V4h4V2h4V0h8v2h4v2h4v2h4v2h4v4h4v4h2v6h2v8h2v70zM8 40h18v22H8zM34 40h18v22H34zM8 68h18v22H8zM34 68h18v22H34z'/%3E%3C/svg%3E\")";
const DOOR_SILHOUETTE_MASK =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 100' shape-rendering='crispEdges'%3E%3Cpath d='M0 100V30h2V22h2V16h2V12h4V8h4V6h4V4h4V2h4V0h8v2h4v2h4v2h4v2h4v4h4v4h2v6h2v8h2v70z'/%3E%3C/svg%3E\")";

const FONT_FACES = `
@font-face { font-family: 'Pixelify Sans'; font-style: normal; font-weight: 400; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TTp0H1Y.ttf') format('truetype'); }
@font-face { font-family: 'Pixelify Sans'; font-style: normal; font-weight: 500; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TTb0H1Y.ttf') format('truetype'); }
@font-face { font-family: 'Pixelify Sans'; font-style: normal; font-weight: 600; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TQ3131Y.ttf') format('truetype'); }
`;

export type DoorTransitionProps = {
  durationInFrames?: number;
  frameOffset?: number;
  progress?: number;
};

const DEFAULT_DURATION = 105;

function DitherField({ phase }: { phase: number }) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "#000",
        backgroundImage:
          "conic-gradient(#4cc3e3 25%, transparent 0 50%, #00607a 0 75%, transparent 0)",
        backgroundPosition: `${phase}px ${phase}px`,
        backgroundSize: "4px 4px",
        mixBlendMode: "normal",
      }}
    />
  );
}

function DoorGlyph() {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "block",
        width: "100%",
        height: "100%",
        background: "#4cc3e3",
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

/**
 * The landing-page door, rebuilt as a frame-pure scene. The optional progress
 * prop is useful when the parent owns the scene clock; frameOffset keeps the
 * same component usable inside a later composition Sequence.
 */
export function DoorTransition({
  durationInFrames = DEFAULT_DURATION,
  frameOffset = 0,
  progress,
}: DoorTransitionProps) {
  const localFrame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const frame = progress == null ? localFrame + frameOffset : progress * durationInFrames;
  const u = Math.min(width / 1920, height / 1080);
  const sec = (seconds: number) => Math.round(seconds * 30);
  const openStart = sec(0.25);
  const openEnd = sec(1.05);
  const pushStart = sec(1.45);
  const pushEnd = sec(3.05);
  const doorOpen = interpolate(frame, [openStart, openEnd], [0, 1], { ...CLAMP, easing: OUT });
  const light = interpolate(frame, [0, openEnd], [0.12, 1], CLAMP);
  const push = interpolate(frame, [pushStart, pushEnd], [1, 10], { ...CLAMP, easing: Easing.inOut(Easing.cubic) });
  const handoff = interpolate(frame, [pushEnd - 10, Math.min(durationInFrames, pushEnd + 8)], [0, 1], CLAMP);
  const hintIn = interpolate(frame, [openStart + 5, openStart + 18], [0, 1], CLAMP);
  const hintOut = interpolate(frame, [pushStart + 28, pushStart + 56], [1, 0], CLAMP);
  const hintOpacity = Math.min(hintIn, hintOut);
  const leafRotation = interpolate(doorOpen, [0, 1], [0, -78], CLAMP);
  const phase = frame >= 0 ? (Math.floor(frame * 0.9) % 6) : 0;
  const doorWidth = 402 * u;
  const doorHeight = 670 * u;
  const leafOpacity = interpolate(frame, [pushStart, pushStart + 12], [1, 0], CLAMP);

  return (
    <AbsoluteFill style={{ background: "#0a0a0a", overflow: "hidden" }}>
      <style>{css + FONT_FACES}</style>
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--brand-background)",
          opacity: interpolate(frame, [0, pushEnd], [0, 0.18], CLAMP),
        }}
      />
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--brand-background)",
          opacity: Math.max(handoff, interpolate(frame, [pushStart, pushStart + 38], [0.08, 1], CLAMP)),
        }}
      />

      <div
        style={{
          position: "absolute",
          left: `${72 * u}px`,
          top: "50%",
          transform: "translateY(-50%)",
          color: "#f2f2f2",
          fontFamily: "'Pixelify Sans', ui-monospace, monospace",
          fontSize: `${78 * u}px`,
          fontWeight: 500,
          letterSpacing: 0,
          lineHeight: 0.92,
          opacity: interpolate(frame, [0, pushEnd, Math.min(durationInFrames, pushEnd + 15)], [0.88, 0.88, 0], CLAMP),
          whiteSpace: "pre-line",
        }}
      >
        Front{`\n`}Door
      </div>

      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: doorWidth,
          height: doorHeight,
          transform: `translate(-50%, -50%) scale(${push})`,
          transformOrigin: "center center",
          perspective: "1100px",
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            background: "var(--brand-background)",
          opacity: light,
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
            opacity: leafOpacity,
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
          <span
            style={{
              position: "absolute",
              right: "12%",
              top: "54%",
              width: "7%",
              aspectRatio: "1",
              background: "#fff",
            }}
          />
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: "50%",
          top: `${50 + 24 * u}%`,
          transform: "translateX(-50%)",
          color: "#c5e11d",
          fontFamily: "'Pixelify Sans', ui-monospace, monospace",
          fontSize: `${26 * u}px`,
          fontWeight: 400,
          lineHeight: 1.35,
          textAlign: "center",
          whiteSpace: "nowrap",
          background: "rgba(20, 23, 28, 0.72)",
          padding: `${6 * u}px ${14 * u}px`,
          borderRadius: "var(--brand-radius)",
          opacity: hintOpacity,
        }}
      >
        Come in, chef. Your kitchen is ready.
      </div>

      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--brand-background)",
          opacity: handoff,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
}

export { DoorGlyph };
