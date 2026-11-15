/*
 * Front Door / Junction 2026 submission.
 * 1920x1080, 30 fps, 1:55. The live-demo slot is one replaceable 62 s take.
 */
import {
  AbsoluteFill,
  Audio,
  Composition,
  Easing,
  Mix,
  Sequence,
  Video,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "raea";
import { Canvas3D, Entity, Screen, manifold } from "raea/3d";
import { Camera3d } from "raea/camera";
import { AmbientLight, DirectionalLight } from "raea/light";
import { Mesh3d } from "raea/mesh";
import { StandardMaterial } from "raea/pbr";
import { Quat, Transform } from "raea/transform";
import { css } from "./styles.gen";
import captionData from "./words.json";
import { CAPTION_BAND_TOP, FPS, TIMELINE, frames, type CaptionCue, type DemoCallout } from "./timeline";
import { ColdOpen as ColdOpenScene } from "./scenes/ColdOpen";
import { Closer as CloserScene } from "./scenes/Closer";
import { DoorTransition as DoorTransitionScene } from "./scenes/DoorTransition";

const OUT = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const FONT_HEADING = "var(--brand-font-heading)";
const FONT_BODY = "var(--brand-font-body)";
const MEDIA = (file: string) => staticFile(file);
const CAPTIONS = captionData as CaptionCue[];
const PHONE_BODY = manifold.roundedBox(1.68, 3.18, 0.24, 0.18);
const DYNAMIC_ISLAND = manifold.roundedBox(0.44, 0.13, 0.04, 0.055);

function fadeIn(frame: number, duration = 8) {
  return interpolate(frame, [0, duration], [0, 1], CLAMP);
}

function Eyebrow({ children, color = "var(--brand-lime)" }: { children: string; color?: string }) {
  return (
    <div style={{ color, fontFamily: FONT_BODY, fontSize: 24, fontWeight: 750, letterSpacing: "0.08em", lineHeight: 1, textTransform: "uppercase" }}>
      {children}
    </div>
  );
}

function CaptionOverlay() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;
  const cue = CAPTIONS.find((item) => time >= item.start && time < item.end);
  const endCardStart = TIMELINE.sections.closer.start + 4.8;
  if (!cue || time >= endCardStart) return null;
  return (
    <div aria-label="caption band" style={{ position: "absolute", left: 0, right: 0, top: CAPTION_BAND_TOP, height: 180, zIndex: 20, pointerEvents: "none" }}>
      <div aria-hidden="true" style={{ position: "absolute", inset: "-70px 0 0", background: "linear-gradient(180deg, rgba(18, 22, 26, 0) 0%, rgba(18, 22, 26, 0.78) 34%, rgba(18, 22, 26, 0.96) 100%)" }} />
      <div style={{ position: "relative", width: 1640, height: 180, margin: "0 auto", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", textAlign: "center", fontFamily: FONT_BODY, textShadow: "0 3px 18px rgba(0,0,0,0.55)" }}>
        <div style={{ color: cue.speaker === "Zoha" ? "var(--brand-lime)" : "#4cc3e3", fontSize: 24, fontWeight: 800, letterSpacing: "0.08em", lineHeight: 1, textTransform: "uppercase", opacity: fadeIn((time - cue.start) * fps, 5) }}>{cue.speaker}</div>
        <div style={{ marginTop: 12, maxWidth: 1600, maxHeight: 112, overflow: "hidden", color: "var(--brand-background)", fontSize: 54, fontWeight: 650, lineHeight: 1.05, opacity: fadeIn((time - cue.start) * fps, 5) }}>{cue.text}</div>
      </div>
    </div>
  );
}

function Explanation() {
  const frame = useCurrentFrame();
  const cards = TIMELINE.explanation.cards;
  const cardFrames = Math.max(1, Math.floor(frames(TIMELINE.sections.explanation.duration) / cards.length));
  const index = Math.min(cards.length - 1, Math.floor(frame / cardFrames));
  const card = cards[index];
  const local = frame - index * cardFrames;
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)", color: "var(--brand-text)", padding: "100px 86px" }}>
      <Eyebrow color="var(--brand-accent)">The handoff</Eyebrow>
      <div style={{ position: "absolute", right: 86, top: 100, color: "var(--brand-ink-faint)", fontFamily: FONT_BODY, fontSize: 24, fontWeight: 700 }}>{String(index + 1).padStart(2, "0")} / 03</div>
      <div style={{ position: "absolute", left: 86, right: 250, top: 212, fontFamily: FONT_HEADING, fontSize: 68, fontWeight: 750, letterSpacing: "-0.04em", lineHeight: 0.98, opacity: fadeIn(local, 8), transform: `translateY(${interpolate(local, [0, 8], [26, 0], { ...CLAMP, easing: OUT })}px)` }}>{card.title}</div>
      <div style={{ position: "absolute", left: 86, right: 340, top: 332, color: "var(--brand-ink-muted)", fontFamily: FONT_BODY, fontSize: 34, lineHeight: 1.16, opacity: fadeIn(local + 5, 10) }}>{card.body}</div>
      <div style={{ position: "absolute", left: 86, right: 86, top: 560, display: "flex", gap: 18 }}>
        {card.steps.map((step, stepIndex) => {
          const stepLocal = local - stepIndex * 6;
          return <div key={step} style={{ flex: 1, minHeight: 116, boxSizing: "border-box", padding: "22px 26px", border: "1px solid var(--brand-line)", borderRadius: "var(--brand-radius)", background: stepIndex === 1 ? "var(--brand-teal-soft)" : "var(--brand-surface)", color: stepIndex === 1 ? "var(--brand-accent)" : "var(--brand-text)", fontFamily: FONT_BODY, fontSize: 28, fontWeight: 750, opacity: fadeIn(stepLocal, 8), transform: `translateY(${interpolate(stepLocal, [0, 8], [16, 0], { ...CLAMP, easing: OUT })}px)` }}>{step}</div>;
        })}
      </div>
    </AbsoluteFill>
  );
}

function keyframeValue(field: "scale" | "rotate", seconds: number) {
  const keyframes = TIMELINE.demo.keyframes;
  return interpolate(seconds, keyframes.map((item) => item.at), keyframes.map((item) => item[field]), CLAMP);
}

function DemoPhone({ frame }: { frame: number }) {
  const seconds = frame / FPS;
  const scale = keyframeValue("scale", seconds);
  const rotation = keyframeValue("rotate", seconds) * Math.PI / 180;
  const cameraZ = interpolate(scale, [0.94, 1.1], [6.5, 5.9], CLAMP);
  return (
    <div style={{ position: "absolute", left: 360, top: 104, width: 800, height: 760 }}>
      <Canvas3D layered>
        <Camera3d transform={Transform.fromXyz(0, 0.08, cameraZ).lookingAt([0, 0, 0])} projection={{ Perspective: { fov: (38 * Math.PI) / 180 } }} />
        <AmbientLight brightness={115} />
        <DirectionalLight transform={Transform.fromXyz(-3, 5, 4).lookingAt([0, 0, 0])} illuminance={10800} shadow_maps_enabled />
        <Entity transform={Transform.IDENTITY.withRotation(Quat.fromEuler("XYZ", 0, rotation, rotation * 0.2)).withScale([scale, scale, scale])}>
          <Mesh3d name="titanium-body" shape={PHONE_BODY}>
            <StandardMaterial base_color="#7c858d" metallic={0.82} perceptual_roughness={0.22} />
          </Mesh3d>
          <Mesh3d name="dynamic-island" transform={Transform.fromXyz(0, 1.39, 0.15)} shape={DYNAMIC_ISLAND}>
            <StandardMaterial base_color="#050609" perceptual_roughness={0.3} />
          </Mesh3d>
          <Screen name="live-demo-screen" position={[0, 0, 0.14]} resolution={[1080, 1920]} size={[1.43, 2.82]} crt={false} background="#080b0f" brightness={1.06}>
            <Video src={MEDIA(TIMELINE.demo.file)} endAt={frames(TIMELINE.demo.duration)} muted style={{ width: 1080, height: 1920, objectFit: "cover", backgroundColor: "#080b0f" }} />
          </Screen>
        </Entity>
      </Canvas3D>
    </div>
  );
}

function Callout({ item }: { item: DemoCallout }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;
  const local = (seconds - item.start) * fps;
  const accent = item.accent === "lime" ? "var(--brand-lime)" : item.accent === "warm" ? "#f1b36c" : "#4cc3e3";
  const isLeft = item.side === "left";
  const visible = interpolate(local, [0, 8, Math.max(9, (item.end - item.start) * fps - 8), (item.end - item.start) * fps], [0, 1, 1, 0], CLAMP);
  return (
    <div style={{ position: "absolute", left: isLeft ? item.labelX : undefined, right: isLeft ? undefined : 76, top: item.labelY, width: 500, opacity: visible, transform: `translateX(${interpolate(local, [0, 8], [isLeft ? -24 : 24, 0], { ...CLAMP, easing: OUT })}px)` }}>
      <div style={{ borderInlineStart: isLeft ? undefined : "5px solid " + accent, borderInlineEnd: isLeft ? "5px solid " + accent : undefined, paddingInlineStart: isLeft ? 0 : 22, paddingInlineEnd: isLeft ? 22 : 0, textAlign: isLeft ? "right" : "left", fontFamily: FONT_BODY }}>
        <div style={{ color: accent, fontSize: 24, fontWeight: 800, letterSpacing: "0.08em", lineHeight: 1 }}>{item.text}</div>
        <div style={{ marginTop: 12, color: "var(--brand-background)", fontSize: 31, fontWeight: 650, lineHeight: 1.12 }}>{item.detail}</div>
      </div>
    </div>
  );
}

function DemoSlot() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;
  const active = TIMELINE.demo.callouts.find((item) => seconds >= item.start && seconds < item.end);
  return (
    <AbsoluteFill style={{ background: "var(--brand-ink)", color: "var(--brand-background)", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 74, top: 72 }}><Eyebrow>Live demo</Eyebrow><div style={{ marginTop: 12, fontFamily: FONT_HEADING, fontSize: 27, fontWeight: 650 }}>one continuous take · real time</div></div>
      <div style={{ position: "absolute", left: 74, top: 184, padding: "12px 18px", borderRadius: 999, background: "var(--brand-lime)", color: "var(--brand-lime-ink)", fontFamily: FONT_BODY, fontSize: 26, fontWeight: 850, letterSpacing: "0.06em" }}>LIVE · one take · real time</div>
      <div aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, top: 866, height: 14, background: "linear-gradient(90deg, transparent, var(--brand-lime), transparent)", opacity: 0.45 }} />
      <DemoPhone frame={frame} />
      {active ? <Callout item={active} /> : null}
    </AbsoluteFill>
  );
}

function GeminiEvidence() {
  const f = useCurrentFrame();
  const progress = interpolate(f, [12, 34], [0, 1], CLAMP);
  return (
    <div style={{ position: "absolute", left: 500, top: 330, right: 92, height: 238, boxSizing: "border-box", padding: "24px 28px", border: "1px solid var(--brand-line)", borderRadius: "var(--brand-radius)", background: "var(--brand-surface)", fontFamily: FONT_BODY }}>
      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--brand-ink-muted)", fontSize: 24, fontWeight: 700 }}><span>confidence → permission</span><span>threshold 0.70</span></div>
      <div style={{ position: "relative", height: 12, marginTop: 30, background: "var(--brand-line)" }}><div style={{ width: "70%", height: "100%", background: "var(--brand-ink-faint)" }} /><div style={{ position: "absolute", left: "70%", top: -12, width: 3, height: 36, background: "var(--brand-lime)" }} /></div>
      <div style={{ display: "flex", gap: 28, marginTop: 26 }}>
        <div style={{ flex: 1, opacity: interpolate(progress, [0, 1], [0.45, 1], CLAMP) }}><div style={{ color: "var(--brand-ink-muted)", fontSize: 22 }}>coffee milk</div><div style={{ marginTop: 6, color: "#b06f4f", fontSize: 34, fontWeight: 800 }}>0.115 · ASK</div></div>
        <div style={{ flex: 1, opacity: interpolate(progress, [0, 1], [0.45, 1], CLAMP) }}><div style={{ color: "var(--brand-ink-muted)", fontSize: 22 }}>lactose-free milk</div><div style={{ marginTop: 6, color: "var(--brand-good)", fontSize: 34, fontWeight: 800 }}>0.897 · ACT</div></div>
      </div>
    </div>
  );
}

function CodexEvidence({ lines }: { lines: readonly string[] }) {
  const f = useCurrentFrame();
  const offset = Math.min(lines.length - 1, Math.floor(interpolate(f, [0, 254], [0, lines.length - 4], CLAMP)));
  return (
    <div style={{ position: "absolute", left: 500, top: 330, right: 92, height: 238, boxSizing: "border-box", padding: "20px 26px", borderRadius: "var(--brand-radius)", background: "#101419", color: "#c4e7ef", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 22, lineHeight: 1.34, overflow: "hidden" }}>
      {lines.slice(offset, offset + 4).map((line, index) => <div key={line} style={{ opacity: fadeIn(f - index * 4, 8), whiteSpace: "nowrap" }}>{index === 0 ? <span style={{ color: "#c5e11d" }}>$ </span> : null}{line}</div>)}
    </div>
  );
}

function CraciEvidence({ build }: { build: { status: string; componentCounts: { pip: number; npm: number }; networkDestinations: number; sbomSha256: string } }) {
  const f = useCurrentFrame();
  const opacity = fadeIn(f, 12);
  return (
    <div style={{ position: "absolute", left: 500, top: 330, right: 92, height: 238, boxSizing: "border-box", padding: "20px 26px", border: "1px solid #1f4b58", borderRadius: "var(--brand-radius)", background: "#0f1e24", color: "#d8f7f5", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 22, lineHeight: 1.42, opacity }}>
      <div style={{ color: "#c5e11d", fontWeight: 800 }}>{"{\"status\":\""}{build.status}{"\","}</div>
      <div>{"  \"component_counts\": { \"pip\": "}{build.componentCounts.pip}{", \"npm\": "}{build.componentCounts.npm}{" },"}</div>
      <div>{"  \"network_destinations\": "}{build.networkDestinations}{","}</div>
      <div>{"  \"sbom_sha256\": \""}{build.sbomSha256}{"…\","}</div>
      <div style={{ marginTop: 8, color: "#8ebec8", fontSize: 19 }}>{"/.well-known/front-door-build.json  ·  curl  ·  signed order → build"}</div>
    </div>
  );
}

function Facts() {
  const frame = useCurrentFrame();
  const cardFrames = Math.max(1, Math.floor(frames(TIMELINE.sections.facts.duration) / TIMELINE.facts.length));
  const index = Math.min(TIMELINE.facts.length - 1, Math.floor(frame / cardFrames));
  const local = frame - index * cardFrames;
  const fact = TIMELINE.facts[index];
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)", color: "var(--brand-text)", padding: "92px 92px" }}>
      <Eyebrow color="var(--brand-accent)">Track fact {String(index + 1).padStart(2, "0")} / 03</Eyebrow>
      <div style={{ position: "absolute", left: 92, top: 160, width: 330, color: "var(--brand-accent)", fontFamily: FONT_HEADING, fontSize: 118, fontWeight: 800, letterSpacing: "-0.06em", lineHeight: 0.82, opacity: fadeIn(local, 8), transform: `translateY(${interpolate(local, [0, 8], [22, 0], { ...CLAMP, easing: OUT })}px)` }}>{fact.number}</div>
      <div style={{ position: "absolute", left: 92, top: 294, color: "var(--brand-text)", fontFamily: FONT_BODY, fontSize: 32, fontWeight: 800, letterSpacing: "0.08em" }}>{fact.label}</div>
      <div style={{ position: "absolute", left: 500, top: 146, right: 100, fontFamily: FONT_HEADING, fontSize: 48, fontWeight: 750, letterSpacing: "-0.035em", lineHeight: 1.02, opacity: fadeIn(local + 4, 10) }}>{fact.headline}</div>
      <div style={{ position: "absolute", left: 500, top: 230, right: 130, color: "var(--brand-ink-muted)", fontFamily: FONT_BODY, fontSize: 28, lineHeight: 1.12, opacity: fadeIn(local + 8, 10) }}>{fact.line}</div>
      {fact.id === "gemini" ? <GeminiEvidence /> : null}
      {fact.id === "codex" ? <CodexEvidence lines={fact.gitLog} /> : null}
      {fact.id === "craci" ? <CraciEvidence build={fact.build} /> : null}
      <div style={{ position: "absolute", left: 92, right: 92, top: 610, display: "flex", flexDirection: "column", gap: 12 }}>
        {fact.facts.map((item, itemIndex) => {
          const itemLocal = local - 18 - itemIndex * 8;
          return <div key={item} style={{ display: "flex", alignItems: "flex-start", gap: 18, minHeight: 66, color: "var(--brand-text)", fontFamily: FONT_BODY, fontSize: 24, lineHeight: 1.16, opacity: fadeIn(itemLocal, 10), transform: `translateY(${interpolate(itemLocal, [0, 10], [14, 0], { ...CLAMP, easing: OUT })}px)` }}><span style={{ flex: "0 0 12px", width: 12, height: 12, marginTop: 7, borderRadius: "50%", background: itemIndex === 1 ? "var(--brand-accent)" : "var(--brand-lime)" }} /><span>{item}</span></div>;
        })}
      </div>
    </AbsoluteFill>
  );
}

function SoundDesign() {
  return <>
    <Sequence from={frames(TIMELINE.sections.door.start)} durationInFrames={frames(1.4)} layout="none" name="door-creak"><Audio src={MEDIA("sfx/door-creak.wav")} gainDb={-18} fadeIn={0.01} fadeOut={0.4} /></Sequence>
    <Sequence from={frames(TIMELINE.sections.door.start + 1.1)} durationInFrames={frames(1.8)} layout="none" name="door-whoosh"><Audio src={MEDIA("sfx/door-whoosh.wav")} gainDb={-16} fadeIn={0.03} fadeOut={0.5} /></Sequence>
    <Sequence from={frames(TIMELINE.sections.demo.start + 25.5)} durationInFrames={frames(0.8)} layout="none" name="held-stamp"><Audio src={MEDIA("sfx/stamp-hit.wav")} gainDb={-20} fadeIn={0.01} fadeOut={0.3} /></Sequence>
    <Sequence from={frames(TIMELINE.sections.demo.start + 51)} durationInFrames={frames(0.8)} layout="none" name="ordered-stamp"><Audio src={MEDIA("sfx/stamp-hit.wav")} gainDb={-19} fadeIn={0.01} fadeOut={0.3} /></Sequence>
  </>;
}

function Voiceover() {
  if (!TIMELINE.voiceover.enabled) return null;
  return <Sequence from={0} durationInFrames={frames(TIMELINE.totalSeconds)} layout="none" name="voiceover"><Audio src={MEDIA(TIMELINE.voiceover.file)} bus="voice" gainDb={0} fadeIn={0.012} fadeOut={1.2} /></Sequence>;
}

function FrontDoor() {
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)" }}>
      <style>{css}</style>
      <Sequence from={frames(TIMELINE.sections.coldOpen.start)} durationInFrames={frames(TIMELINE.sections.coldOpen.duration)} name="cold open"><ColdOpenScene durationInFrames={frames(TIMELINE.sections.coldOpen.duration)} /></Sequence>
      <Sequence from={frames(TIMELINE.sections.door.start)} durationInFrames={frames(TIMELINE.sections.door.duration)} name="door transition"><DoorTransitionScene durationInFrames={frames(TIMELINE.sections.door.duration)} /></Sequence>
      <Sequence from={frames(TIMELINE.sections.explanation.start)} durationInFrames={frames(TIMELINE.sections.explanation.duration)} name="explanation"><Explanation /></Sequence>
      <Sequence from={frames(TIMELINE.sections.demo.start)} durationInFrames={frames(TIMELINE.sections.demo.duration)} name="live demo slot"><DemoSlot /></Sequence>
      <Sequence from={frames(TIMELINE.sections.facts.start)} durationInFrames={frames(TIMELINE.sections.facts.duration)} name="track facts"><Facts /></Sequence>
      <Sequence from={frames(TIMELINE.sections.closer.start)} durationInFrames={frames(TIMELINE.sections.closer.duration)} name="closer"><CloserScene durationInFrames={frames(TIMELINE.sections.closer.duration)} /></Sequence>
      <SoundDesign />
      <Voiceover />
      <CaptionOverlay />
      <Mix lufs={-14} ceiling={-1.5} />
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="front-door" component={FrontDoor} width={1920} height={1080} fps={FPS} durationInFrames={frames(TIMELINE.totalSeconds)} />);
