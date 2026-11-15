/*
 * Front Door / Junction 2026 submission template.
 * 1920x1080, 30 fps, 1:57 (3510 frames). Timing and replaceable live-demo data live in timeline.ts.
 */
import {
  AbsoluteFill,
  Audio,
  Composition,
  Easing,
  Img,
  Mix,
  Sequence,
  Video,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "raea";
import { css } from "./styles.gen";
import captionData from "./words.json";
import { FPS, TIMELINE, type CaptionCue, frames } from "./timeline";

const OUT = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const FONT_HEADING = "var(--brand-font-heading)";
const FONT_BODY = "var(--brand-font-body)";
const MEDIA = (file: string) => staticFile(file);

const CAPTIONS = captionData as CaptionCue[];

function fadeIn(frame: number, duration = 8) {
  return interpolate(frame, [0, duration], [0, 1], CLAMP);
}

function Eyebrow({ children, color = "var(--brand-lime)" }: { children: string; color?: string }) {
  return (
    <div style={{
      color,
      fontFamily: FONT_BODY,
      fontSize: "calc(24px * var(--video-scale))",
      fontWeight: 700,
      letterSpacing: "0.08em",
      lineHeight: 1,
      textTransform: "uppercase",
    }}>
      {children}
    </div>
  );
}

function CaptionOverlay() {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const time = frame / fps;
  const cue = CAPTIONS.find((item) => time >= item.start && time < item.end);
  const endCardStart = TIMELINE.sections.closer.start + 4;
  if (!cue || time >= endCardStart) return null;
  const u = width / 1920;
  const bottom = time < TIMELINE.sections.coldOpen.duration ? 330 : 150;
  return (
    <div style={{
      position: "absolute",
      left: 270 * u,
      right: 270 * u,
      bottom: bottom * u,
      padding: `${16 * u}px ${26 * u}px ${18 * u}px`,
      borderRadius: "var(--brand-radius)",
      background: "var(--brand-veil)",
      color: "var(--brand-background)",
      fontFamily: FONT_BODY,
      fontSize: `${64 * u}px`,
      fontWeight: 600,
      lineHeight: 1.1,
      textAlign: "center",
      opacity: fadeIn((time - cue.start) * fps, 5),
    }}>
      <span style={{ color: cue.speaker === "Zoha" ? "var(--brand-lime)" : "var(--brand-background)", marginInlineEnd: `${12 * u}px` }}>{cue.speaker}</span>
      {cue.text}
    </div>
  );
}

/** The cold open keeps the supplied illustration and its original audio intact. */
function ColdOpen() {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const u = width / 1920;
  return (
    <AbsoluteFill style={{ background: "var(--brand-ink)", opacity: interpolate(frame, [0, 6], [0.4, 1], CLAMP), overflow: "hidden" }}>
      <Video
        src={MEDIA("coldopen-b.mp4")}
        endAt={frames(8)}
        gainDb={-2}
        fadeIn={0.012}
        fadeOut={0.2}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />
      <div style={{ position: "absolute", inset: 0, background: "var(--brand-veil-soft)" }} />
      <div style={{ position: "absolute", top: 140 * u, left: 72 * u, padding: `${12 * u}px ${18 * u}px`, border: "1px solid var(--brand-paper-soft)", borderRadius: "var(--brand-radius)", color: "var(--brand-background)", fontFamily: FONT_BODY, fontSize: `${28 * u}px`, fontWeight: 600 }}>
        Illustration · AI-generated
      </div>
      <div style={{ position: "absolute", left: 72 * u, right: 72 * u, bottom: 160 * u, color: "var(--brand-background)", fontFamily: FONT_HEADING, fontSize: `${72 * u}px`, fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 0.98 }}>
        06:00 · 500 guests · cut-off closing
      </div>
    </AbsoluteFill>
  );
}

/** Two restrained panels swing apart to reveal the product and its promise. */
function DoorTransition() {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const u = width / 1920;
  const progress = interpolate(frame, [0, frames(2.5)], [0, 1], { ...CLAMP, easing: OUT });
  const leftX = interpolate(progress, [0, 1], [0, -50]);
  const rightX = interpolate(progress, [0, 1], [0, 50]);
  const light = interpolate(progress, [0, 1], [0, 1], CLAMP);
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: "var(--brand-background)", opacity: light }} />
      <div style={{ position: "absolute", left: 72 * u, right: 72 * u, top: 245 * u, textAlign: "center", color: "var(--brand-accent)", opacity: light, transform: `translateY(${interpolate(progress, [0, 1], [24, 0], CLAMP)}px)` }}>
        <div style={{ fontFamily: FONT_HEADING, fontSize: `${82 * u}px`, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 0.95 }}>FRONT DOOR</div>
        <div style={{ marginTop: 26 * u, fontFamily: FONT_BODY, fontSize: `${34 * u}px`, fontWeight: 600 }}>Agents knock. The door checks. The chef decides.</div>
      </div>
      <div style={{ position: "absolute", left: 0, top: 0, width: "50%", height: "100%", background: "var(--brand-accent)", transformOrigin: "left center", transform: `translateX(${leftX}%) rotateY(${interpolate(progress, [0, 1], [0, -14], CLAMP)}deg)`, boxShadow: "18px 0 0 var(--brand-lime)" }} />
      <div style={{ position: "absolute", right: 0, top: 0, width: "50%", height: "100%", background: "var(--brand-accent)", transformOrigin: "right center", transform: `translateX(${rightX}%) rotateY(${interpolate(progress, [0, 1], [0, 14], CLAMP)}deg)`, boxShadow: "-18px 0 0 var(--brand-lime)" }} />
      <div style={{ position: "absolute", left: "50%", top: 0, width: 6 * u, height, transform: "translateX(-50%)", background: "var(--brand-lime)", opacity: 1 - light }} />
    </AbsoluteFill>
  );
}

/** Type-driven explanation cards establish the problem, the check, and the hand-back. */
function Explanation() {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const u = width / 1920;
  const cards = TIMELINE.explanation.cards;
  const cardFrames = frames(TIMELINE.sections.explanation.duration / cards.length);
  const index = Math.min(cards.length - 1, Math.floor(frame / cardFrames));
  const card = cards[index];
  const local = frame - index * cardFrames;
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)", color: "var(--brand-text)", padding: `${130 * u}px ${86 * u}px ${130 * u}px` }}>
      <Eyebrow color="var(--brand-accent)">The handoff</Eyebrow>
      <div style={{ marginTop: 68 * u, maxWidth: 1180 * u, fontFamily: FONT_HEADING, fontSize: `${70 * u}px`, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 0.98, opacity: fadeIn(local, 8), transform: `translateY(${interpolate(local, [0, 8], [28, 0], { ...CLAMP, easing: OUT })}px)` }}>
        {card.title}
      </div>
      <div style={{ marginTop: 34 * u, maxWidth: 980 * u, fontFamily: FONT_BODY, fontSize: `${34 * u}px`, lineHeight: 1.15, color: "var(--brand-ink-muted)", opacity: fadeIn(local, 12) }}>
        {card.body}
      </div>
      <div style={{ position: "absolute", left: 86 * u, right: 86 * u, bottom: 180 * u, display: "flex", gap: 18 * u }}>
        {card.steps.map((step, stepIndex) => (
          <div key={step} style={{ flex: 1, minHeight: 100 * u, padding: `${22 * u}px ${26 * u}px`, border: "1px solid var(--brand-line)", borderRadius: "var(--brand-radius)", background: stepIndex === 1 ? "var(--brand-teal-soft)" : "var(--brand-surface)", color: stepIndex === 1 ? "var(--brand-accent)" : "var(--brand-text)", fontFamily: FONT_BODY, fontSize: `${28 * u}px`, fontWeight: 650, opacity: fadeIn(local - stepIndex * 6, 8), transform: `translateY(${interpolate(local - stepIndex * 6, [0, 8], [18, 0], { ...CLAMP, easing: OUT })}px)` }}>
            {step}
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", right: 86 * u, top: 130 * u, fontFamily: FONT_BODY, fontSize: `${28 * u}px`, fontWeight: 600, color: "var(--brand-ink-faint)" }}>{String(index + 1).padStart(2, "0")} / 03</div>
    </AbsoluteFill>
  );
}

function DemoVideo() {
  const { width, height } = useVideoConfig();
  const u = width / 1920;
  const crop = TIMELINE.demo.crop;
  const cropWidth = `${100 / crop.width}%`;
  const cropHeight = `${100 / crop.height}%`;
  const cropLeft = `${(-crop.x / crop.width) * 100}%`;
  const cropTop = `${(-crop.y / crop.height) * 100}%`;
  return (
    <div style={{ position: "absolute", left: 74 * u, top: 228 * u, width: 1110 * u, height: 624 * u, border: "1px solid var(--brand-ink-faint)", borderRadius: "var(--brand-radius)", background: "var(--brand-ink)", overflow: "hidden", boxShadow: "0 18px 42px rgb(0 0 0 / 0.22)" }}>
      <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
        <Video src={MEDIA(TIMELINE.demo.file)} muted style={{ position: "absolute", left: cropLeft, top: cropTop, width: cropWidth, height: cropHeight, objectFit: "cover" }} />
      </div>
      <div style={{ position: "absolute", inset: 0, border: "10px solid var(--brand-ink)", borderRadius: "var(--brand-radius)", pointerEvents: "none" }} />
    </div>
  );
}

/** The live take frame keeps the replaceable demo central and the narrative labels stable. */
function DemoSlot() {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const u = width / 1920;
  const seconds = frame / fps;
  const active = TIMELINE.demo.callouts.find((item) => seconds >= item.start && seconds < item.end);
  const speed = TIMELINE.demo.speedRanges.find((item) => seconds >= item.start && seconds < item.end);
  return (
    <AbsoluteFill style={{ background: "var(--brand-ink)", color: "var(--brand-background)" }}>
      <div style={{ position: "absolute", left: 74 * u, top: 132 * u }}><Eyebrow>Live demo</Eyebrow></div>
      <div style={{ position: "absolute", left: 74 * u, top: 172 * u, fontFamily: FONT_HEADING, fontSize: `${32 * u}px`, fontWeight: 650, letterSpacing: "-0.02em" }}>one continuous take · placeholder</div>
      <DemoVideo />
      <div style={{ position: "absolute", left: 100 * u, top: 258 * u, padding: `${12 * u}px ${18 * u}px`, borderRadius: 999, background: "var(--brand-lime)", color: "var(--brand-lime-ink)", fontFamily: FONT_BODY, fontSize: `${28 * u}px`, fontWeight: 800, letterSpacing: "0.08em" }}>LIVE · one take</div>
      {speed ? <div style={{ position: "absolute", left: 100 * u, top: 708 * u, padding: `${10 * u}px ${16 * u}px`, borderRadius: 999, background: "var(--brand-lime)", color: "var(--brand-lime-ink)", fontFamily: FONT_BODY, fontSize: `${26 * u}px`, fontWeight: 800 }}>{`×${speed.rate}`}</div> : null}
      {active ? (
        <div style={{ position: "absolute", left: 1260 * u, right: 78 * u, top: 330 * u, padding: `${28 * u}px ${32 * u}px`, borderInlineStart: `${6 * u}px solid var(--brand-lime)`, background: "var(--brand-veil-soft)", color: "var(--brand-background)", fontFamily: FONT_BODY, fontSize: `${34 * u}px`, fontWeight: 650, lineHeight: 1.08, opacity: fadeIn((seconds - active.start) * fps, 8), transform: `translateX(${interpolate((seconds - active.start) * fps, [0, 8], [28, 0], { ...CLAMP, easing: OUT })}px)` }}>
          {active.text}
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 1260 * u, right: 78 * u, bottom: 190 * u, color: "var(--brand-background)", fontFamily: FONT_BODY, fontSize: `${26 * u}px`, lineHeight: 1.25 }}>
        Gemini reads the list.<br />
        Valio answers with facts.<br />
        The chef decides.
      </div>
    </AbsoluteFill>
  );
}

/** One fact card at a time makes the three proof points easy to read. */
function Facts() {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const u = width / 1920;
  const cardFrames = frames(TIMELINE.sections.facts.duration / TIMELINE.facts.length);
  const index = Math.min(TIMELINE.facts.length - 1, Math.floor(frame / cardFrames));
  const local = frame - index * cardFrames;
  const fact = TIMELINE.facts[index];
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)", color: "var(--brand-text)", padding: `${130 * u}px ${92 * u}px` }}>
      <Eyebrow color="var(--brand-accent)">Track fact {String(index + 1).padStart(2, "0")} / 03</Eyebrow>
      <div style={{ position: "absolute", left: 92 * u, top: 290 * u, width: 430 * u, fontFamily: FONT_HEADING, fontSize: `${78 * u}px`, fontWeight: 700, letterSpacing: "-0.04em", color: "var(--brand-accent)", opacity: fadeIn(local, 8), transform: `translateY(${interpolate(local, [0, 8], [24, 0], { ...CLAMP, easing: OUT })}px)` }}>{fact.label}</div>
      <div style={{ position: "absolute", left: 585 * u, top: 250 * u, right: 120 * u, fontFamily: FONT_HEADING, fontSize: `${56 * u}px`, fontWeight: 700, letterSpacing: "-0.035em", lineHeight: 1, opacity: fadeIn(local + 4, 10) }}>{fact.headline}</div>
      <div style={{ position: "absolute", left: 585 * u, top: 486 * u, right: 180 * u, fontFamily: FONT_BODY, fontSize: `${34 * u}px`, lineHeight: 1.18, color: "var(--brand-ink-muted)", opacity: fadeIn(local + 8, 12) }}>{fact.body}</div>
      <div style={{ position: "absolute", left: 92 * u, right: 92 * u, bottom: 168 * u, height: 8 * u, background: "var(--brand-line)" }}>
        <div style={{ width: `${interpolate(local, [0, cardFrames], [0, 100], CLAMP)}%`, height: "100%", background: "var(--brand-lime)" }} />
      </div>
    </AbsoluteFill>
  );
}

/** The closer returns to the hand, then leaves the URLs and the non-payment disclaimer. */
function Closer() {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const u = width / 1920;
  const endShotFrames = frames(4);
  if (frame < endShotFrames) {
    return (
      <AbsoluteFill style={{ background: "var(--brand-ink)", overflow: "hidden" }}>
        <Video src={MEDIA("coldopen-b.mp4")} startFrom={frames(TIMELINE.closer.coldOpenStart)} endAt={frames(8)} gainDb={-4} fadeOut={0.2} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", transform: `scale(${interpolate(frame, [0, endShotFrames], [1, 1.05], CLAMP)})` }} />
        <div style={{ position: "absolute", inset: 0, background: "var(--brand-veil-soft)" }} />
        <div style={{ position: "absolute", left: 72 * u, top: 132 * u, color: "var(--brand-background)", fontFamily: FONT_HEADING, fontSize: `${66 * u}px`, fontWeight: 700 }}>The chef is still in control.</div>
      </AbsoluteFill>
    );
  }
  const local = frame - endShotFrames;
  return (
    <AbsoluteFill style={{ background: "var(--brand-accent)", color: "var(--brand-background)", padding: `${132 * u}px ${84 * u}px`, opacity: fadeIn(local, 8) }}>
      <Eyebrow>Front Door · Valio challenge mock</Eyebrow>
      <div style={{ marginTop: 82 * u, maxWidth: 1340 * u, fontFamily: FONT_HEADING, fontSize: `${86 * u}px`, fontWeight: 700, letterSpacing: "-0.045em", lineHeight: 0.94 }}>Agents knock.<br />The door checks.<br />The chef decides.</div>
      <div style={{ position: "absolute", left: 84 * u, right: 84 * u, bottom: 160 * u, display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 36 * u, fontFamily: FONT_BODY, fontSize: `${24 * u}px`, lineHeight: 1.25, color: "var(--brand-background)" }}>
        <div>
          <div>{TIMELINE.closer.repo}</div>
          <div>{TIMELINE.closer.site}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div>{TIMELINE.closer.disclaimer}</div>
          <div>{TIMELINE.closer.team}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

function Voiceover() {
  if (!TIMELINE.voiceover.enabled) return null;
  return (
    <Sequence from={0} durationInFrames={frames(TIMELINE.totalSeconds)} layout="none" name="voiceover">
      <Audio src={MEDIA(TIMELINE.voiceover.file)} bus="voice" gainDb={0} fadeIn={0.012} fadeOut={1.2} />
    </Sequence>
  );
}

function FrontDoor() {
  const { width } = useVideoConfig();
  const scale = width / 1920;
  return (
    <AbsoluteFill style={{ background: "var(--brand-background)" }}>
      <style>{css}</style>
      <div style={{ position: "absolute", inset: 0, ["--video-scale" as string]: `${scale}` }}>
        <Sequence from={frames(TIMELINE.sections.coldOpen.start)} durationInFrames={frames(TIMELINE.sections.coldOpen.duration)} name="cold open"><ColdOpen /></Sequence>
        <Sequence from={frames(TIMELINE.sections.door.start)} durationInFrames={frames(TIMELINE.sections.door.duration)} name="door transition"><DoorTransition /></Sequence>
        <Sequence from={frames(TIMELINE.sections.explanation.start)} durationInFrames={frames(TIMELINE.sections.explanation.duration)} name="explanation"><Explanation /></Sequence>
        <Sequence from={frames(TIMELINE.sections.demo.start)} durationInFrames={frames(TIMELINE.sections.demo.duration)} name="live demo slot"><DemoSlot /></Sequence>
        <Sequence from={frames(TIMELINE.sections.facts.start)} durationInFrames={frames(TIMELINE.sections.facts.duration)} name="track facts"><Facts /></Sequence>
        <Sequence from={frames(TIMELINE.sections.closer.start)} durationInFrames={frames(TIMELINE.sections.closer.duration)} name="closer"><Closer /></Sequence>
        <Voiceover />
        <CaptionOverlay />
      </div>
      <Mix lufs={-14} ceiling={-1.5} />
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="front-door" component={FrontDoor} width={1920} height={1080} fps={FPS} durationInFrames={frames(TIMELINE.totalSeconds)} />);

