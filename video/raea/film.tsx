/*
 * Front Door · Junction 2026 submission film (control-room cut, written by Claude).
 * 1920x1080, 30 fps, 1:53. One design system: ink stage, paper title, teal + lime, Pixelify for labels.
 * Swap the live take: replace media/demo.mp4 (portrait phone recording) and set BEATS below.
 */
import { AbsoluteFill, Audio, Composition, Easing, Mix, Sequence, Video, interpolate, registerRoot, staticFile, useCurrentFrame } from "raea";
import { DoorTransition } from "./scenes/DoorTransition";
import { Closer } from "./scenes/Closer";

const FPS = 30;
const f = (s: number) => Math.round(s * FPS);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const OUT = Easing.out(Easing.cubic);
const INOUT = Easing.inOut(Easing.cubic);
const ease = (fr: number, a: number, b: number, from = 0, to = 1, e = OUT) => interpolate(fr, [a, b], [from, to], { ...CLAMP, easing: e });

const INK = "#0f1215";
const INK_2 = "#171b20";
const PAPER = "#f6f3ec";
const TEAL = "#4cc3e3";
const TEAL_DEEP = "#00607a";
const LIME = "#c5e11d";
const AMBER = "#f0a85b";
const MUTED = "#9aa3ad";
const SANS = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif";
const PIXEL = "'Pixelify Sans', ui-monospace, monospace";
const MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, monospace";
const FONTS = `
@font-face { font-family: 'Pixelify Sans'; font-weight: 400; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TTp0H1Y.ttf') format('truetype'); }
@font-face { font-family: 'Pixelify Sans'; font-weight: 500; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TTb0H1Y.ttf') format('truetype'); }
@font-face { font-family: 'Pixelify Sans'; font-weight: 600; src: url('media/ai/CHy2V-3HFUT7aC4iv1TxGDR9DHEserHN25py2TQ3131Y.ttf') format('truetype'); }
`;
const DOOR_PATH = "M0 100V30h2V22h2V16h2V12h4V8h4V6h4V4h4V2h4V0h8v2h4v2h4v2h4v2h4v4h4v4h2v6h2v8h2v70zM8 40h18v22H8zM34 40h18v22H34zM8 68h18v22H8zM34 68h18v22H34z";

/* ---------- timeline (seconds) ---------- */
const T = {
  shot: { start: 0, dur: 4 },
  insert: { start: 4, dur: 3.6 },
  door: { start: 7.6, dur: 3.5 },
  title: { start: 11.1, dur: 6.4 },
  demo: { start: 17.5, dur: 62 },
  gemini: { start: 79.5, dur: 8.5 },
  codex: { start: 88, dur: 8.5 },
  craci: { start: 96.5, dur: 8.5 },
  closer: { start: 105, dur: 9 },
};
const TOTAL = T.closer.start + T.closer.dur;

/* Demo beats, seconds into the take. Edit these to the real take (or paste from video/demo-capture/beats.json). */
const BEATS = [
  { t: 0, n: "01", title: "The door opens", detail: "The chef's agent comes in through Valio's front door." },
  { t: 5, n: "02", title: "A photo of a handwritten list", detail: "Seven lines in Finnish, written at the pass. One line is a planted order to the AI." },
  { t: 13, n: "03", title: "Gemini reads it", detail: "Every item, amount and unit. The planted line is flagged and ignored." },
  { t: 21, n: "04", title: "Live Valio facts", detail: "Real product, live price, stock, delivery day and pack size for each line." },
  { t: 30, n: "05", title: "Held for the chef", detail: "Over the kitchen's €1,500 limit. The reason is on the card, not hidden." },
  { t: 38, n: "06", title: "A change in plain words", detail: "“Change the potatoes to 30 kilograms.” The card updates and stays held." },
  { t: 47, n: "07", title: "The chef approves", detail: "Only the chef's tap can approve. The agent never can." },
  { t: 53, n: "08", title: "Ordered · signed", detail: "Signed with Ed25519, tied to the build that made it, kept in the audit log." },
];

/* Captions: who says what, absolute seconds. Re-time after the voiceover is recorded. */
const CAPTIONS: { s: number; e: number; who: "Omar" | "Zoha"; text: string }[] = [
  { s: 0.4, e: 3.9, who: "Zoha", text: "Six in the morning. Five hundred guests on Monday." },
  { s: 4.2, e: 7.4, who: "Zoha", text: "Valio's cut-off is at ten, and nothing is ordered yet." },
  { s: 11.4, e: 14.3, who: "Omar", text: "Front Door lets an AI agent order from Valio" },
  { s: 14.3, e: 17.3, who: "Omar", text: "while the chef keeps the final say." },
  { s: 18.0, e: 22.0, who: "Omar", text: "This is one live take, in real time, on my phone." },
  { s: 22.5, e: 27.5, who: "Zoha", text: "Omar photographs a handwritten list in Finnish." },
  { s: 30.5, e: 37.5, who: "Zoha", text: "Gemini reads every line, and ignores the note telling it to approve everything." },
  { s: 38.5, e: 46.5, who: "Omar", text: "Each item is checked against Valio: product, price, stock and delivery day." },
  { s: 47.5, e: 54.5, who: "Zoha", text: "It's over the kitchen's limit, so the door holds it for the chef." },
  { s: 55.5, e: 63.5, who: "Omar", text: "I change the potatoes by voice. The card updates, still held." },
  { s: 64.5, e: 70.5, who: "Zoha", text: "Only the chef can approve. The agent can't, by design." },
  { s: 71.0, e: 78.5, who: "Omar", text: "Ordered and signed, with the build that signed it on record." },
  { s: 80.0, e: 87.5, who: "Zoha", text: "Gemini scores its own doubt. Below 0.70, it asks the chef instead of guessing." },
  { s: 88.5, e: 95.8, who: "Omar", text: "Codex built the engine and attacked it. Forty-two commits on main." },
  { s: 97.0, e: 104.5, who: "Zoha", text: "CRACI runs our CI, so every order knows which build signed it." },
  { s: 105.5, e: 109.5, who: "Omar", text: "The order is in before the cut-off." },
];

/* ---------- shared pieces ---------- */
function DoorGlyph({ size, color = TEAL }: { size: number; color?: string }) {
  return (
    <svg width={size * 0.6} height={size} viewBox="0 0 60 100" shapeRendering="crispEdges" style={{ display: "block" }}>
      <path fill={color} fillRule="evenodd" d={DOOR_PATH} />
    </svg>
  );
}

function Label({ children, color = TEAL, size = 26 }: { children: string; color?: string; size?: number }) {
  return <div style={{ fontFamily: PIXEL, fontWeight: 500, fontSize: size, letterSpacing: "0.04em", color, lineHeight: 1 }}>{children}</div>;
}

function AiTag() {
  return <div style={{ position: "absolute", left: 40, top: 34, padding: "7px 12px", borderRadius: 8, background: "rgba(10,12,15,0.55)", color: "rgba(255,255,255,0.82)", fontFamily: SANS, fontSize: 18, fontWeight: 600, letterSpacing: "0.02em" }}>Illustration · AI-generated</div>;
}

/* A modern iPhone drawn in CSS: titanium band, black bezel, dynamic island, buttons, glass sheen, floor shadow. */
function IPhone({ height, children, tilt = 0, glow = 0 }: { height: number; children: React.ReactNode; tilt?: number; glow?: number }) {
  const w = height * 0.4878;
  const r = height * 0.083;
  const band = height * 0.0105;
  const bezel = height * 0.0125;
  return (
    <div style={{ position: "relative", width: w, height, transform: `perspective(2400px) rotateY(${tilt}deg)`, transformOrigin: "50% 50%" }}>
      <div style={{ position: "absolute", left: "8%", right: "8%", bottom: -height * 0.05, height: height * 0.07, borderRadius: "50%", background: "radial-gradient(ellipse at center, rgba(0,0,0,0.55), rgba(0,0,0,0) 70%)" }} />
      {glow > 0 ? <div style={{ position: "absolute", inset: -height * 0.12, borderRadius: r * 2, background: `radial-gradient(ellipse at center, rgba(76,195,227,${0.22 * glow}), rgba(76,195,227,0) 65%)` }} /> : null}
      {/* side buttons */}
      <div style={{ position: "absolute", left: -band * 0.9, top: height * 0.17, width: band * 1.2, height: height * 0.04, borderRadius: 3, background: "#5d636b" }} />
      <div style={{ position: "absolute", left: -band * 0.9, top: height * 0.235, width: band * 1.2, height: height * 0.075, borderRadius: 3, background: "#5d636b" }} />
      <div style={{ position: "absolute", left: -band * 0.9, top: height * 0.325, width: band * 1.2, height: height * 0.075, borderRadius: 3, background: "#5d636b" }} />
      <div style={{ position: "absolute", right: -band * 0.9, top: height * 0.27, width: band * 1.2, height: height * 0.11, borderRadius: 3, background: "#5d636b" }} />
      {/* titanium band */}
      <div style={{ position: "absolute", inset: 0, borderRadius: r, background: "linear-gradient(135deg, #9aa1a9 0%, #4d5259 22%, #2a2d32 50%, #5b6168 78%, #a3aab2 100%)", boxShadow: "0 40px 80px rgba(0,0,0,0.45), 0 12px 24px rgba(0,0,0,0.35)" }} />
      {/* black bezel */}
      <div style={{ position: "absolute", inset: band, borderRadius: r - band, background: "#050608" }} />
      {/* screen */}
      <div style={{ position: "absolute", inset: band + bezel, borderRadius: r - band - bezel * 0.6, overflow: "hidden", background: "#000" }}>
        {children}
        {/* glass sheen */}
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(115deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.03) 28%, rgba(255,255,255,0) 42%)", pointerEvents: "none" }} />
      </div>
      {/* dynamic island */}
      <div style={{ position: "absolute", left: "50%", top: band + bezel + height * 0.012, width: w * 0.3, height: height * 0.036, marginLeft: -w * 0.15, borderRadius: 999, background: "#000" }} />
    </div>
  );
}

function Captions() {
  const fr = useCurrentFrame();
  const t = fr / FPS;
  const cue = CAPTIONS.find((c) => t >= c.s && t < c.e);
  if (!cue) return null;
  const local = (t - cue.s) * FPS;
  const out = (cue.e - t) * FPS;
  const o = Math.min(ease(local, 0, 5), ease(out, 0, 5));
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 44, display: "flex", justifyContent: "center", opacity: o, zIndex: 50 }}>
      <div style={{ maxWidth: 1500, padding: "12px 24px 14px", borderRadius: 14, background: "rgba(10,12,15,0.74)", display: "flex", alignItems: "baseline", gap: 14 }}>
        <span style={{ fontFamily: PIXEL, fontSize: 24, color: cue.who === "Omar" ? TEAL : LIME, whiteSpace: "nowrap" }}>{cue.who}</span>
        <span style={{ fontFamily: SANS, fontSize: 38, fontWeight: 600, color: "#fff", lineHeight: 1.18 }}>{cue.text}</span>
      </div>
    </div>
  );
}

/* ---------- 1. cold open: the shot, then a clean insert of the phone ---------- */
function ColdShot() {
  const fr = useCurrentFrame();
  const scale = interpolate(fr, [0, f(T.shot.dur)], [1.0, 1.07], CLAMP);
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${scale})`, transformOrigin: "52% 55%" }}>
        <Video src={staticFile("coldopen/candidate-a.mp4")} endAt={f(T.shot.dur)} gainDb={-6} fadeIn={0.02} fadeOut={0.2} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at 55% 50%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.45) 100%)" }} />
      <AiTag />
      <div style={{ position: "absolute", right: 56, top: 40, fontFamily: PIXEL, fontSize: 44, color: "rgba(255,255,255,0.92)", opacity: ease(fr, 8, 20) }}>06:00</div>
    </AbsoluteFill>
  );
}

function LockScreen({ fr }: { fr: number }) {
  const arrive = f(0.55);
  const local = fr - arrive;
  const y = interpolate(local, [0, 9, 14], [-120, 8, 0], { ...CLAMP, easing: OUT });
  const o = ease(local, 0, 6);
  return (
    <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at 30% 10%, #1e3a46 0%, #0d1418 55%, #07090b 100%)", fontFamily: SANS, color: "#fff" }}>
      <div style={{ position: "absolute", top: "13%", width: "100%", textAlign: "center", fontSize: 22, fontWeight: 600, opacity: 0.85 }}>Monday 16 November</div>
      <div style={{ position: "absolute", top: "16.5%", width: "100%", textAlign: "center", fontSize: 108, fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 1 }}>6:00</div>
      <div style={{ position: "absolute", left: "4.5%", right: "4.5%", top: "38%", transform: `translateY(${y}px)`, opacity: o, borderRadius: 26, padding: "18px 18px 20px", background: "rgba(48,54,60,0.86)", boxShadow: "0 10px 30px rgba(0,0,0,0.35)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 9, background: "#0b2f3a", display: "flex", alignItems: "center", justifyContent: "center" }}><DoorGlyph size={22} /></div>
          <div style={{ flex: 1, fontSize: 18, fontWeight: 600, color: "rgba(255,255,255,0.72)", letterSpacing: "0.02em" }}>REMINDERS</div>
          <div style={{ fontSize: 17, color: "rgba(255,255,255,0.6)" }}>now</div>
        </div>
        <div style={{ marginTop: 12, fontSize: 25, fontWeight: 700, lineHeight: 1.2 }}>Monday order · 500 guests</div>
        <div style={{ marginTop: 4, fontSize: 23, lineHeight: 1.28, color: "rgba(255,255,255,0.88)" }}>Valio cut-off at 10:00. Order still not placed.</div>
      </div>
    </div>
  );
}

function ColdInsert() {
  const fr = useCurrentFrame();
  const push = interpolate(fr, [0, f(T.insert.dur)], [1.0, 1.07], { ...CLAMP, easing: INOUT });
  const tilt = interpolate(fr, [0, f(T.insert.dur)], [-6, 0], { ...CLAMP, easing: INOUT });
  const fadeOut = ease(fr, f(T.insert.dur) - 6, f(T.insert.dur), 1, 0);
  return (
    <AbsoluteFill style={{ background: "#05070a", overflow: "hidden" }}>
      <Video src={staticFile("coldopen/candidate-a.mp4")} endAt={f(T.insert.dur)} muted style={{ position: "absolute", inset: -40, width: 2000, height: 1160, objectFit: "cover", filter: "blur(22px) brightness(0.45) saturate(0.8)" }} />
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${push})`, opacity: fadeOut }}>
        <IPhone height={800} tilt={tilt}><LockScreen fr={fr} /></IPhone>
      </div>
      <AiTag />
      <Sequence from={f(0.55)} durationInFrames={f(1.2)} layout="none" name="chime"><Audio src={staticFile("coldopen/notification-chime.wav")} gainDb={-14} fadeIn={0.01} fadeOut={0.4} /></Sequence>
    </AbsoluteFill>
  );
}

/* ---------- 3. title: what it is, and what we built it with ---------- */
function TitleCard() {
  const fr = useCurrentFrame();
  const tools = [
    { name: "Gemini", role: "reads, scores and talks", color: TEAL_DEEP },
    { name: "Codex", role: "built and attacked the code", color: "#1c1f23" },
    { name: "CRACI", role: "proves which build signed the order", color: "#3d6b00" },
  ];
  return (
    <AbsoluteFill style={{ background: PAPER, color: "#16191d", fontFamily: SANS, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: `repeating-linear-gradient(180deg, rgba(0,96,122,0.0) 0px, rgba(0,96,122,0.0) 53px, rgba(0,96,122,0.07) 54px)`, opacity: ease(fr, 0, 12) }} />
      <div style={{ position: "absolute", left: 150, top: 120, display: "flex", alignItems: "flex-end", gap: 44, opacity: ease(fr, 2, 12), transform: `translateY(${ease(fr, 2, 14, 30, 0)}px)` }}>
        <DoorGlyph size={250} color={TEAL_DEEP} />
        <div>
          <Label color={TEAL_DEEP} size={30}>Valio Aimo · Trusted Trade Agents</Label>
          <div style={{ marginTop: 16, fontSize: 150, fontWeight: 800, letterSpacing: "-0.045em", lineHeight: 0.88 }}>Front Door</div>
          <div style={{ marginTop: 22, fontSize: 44, fontWeight: 500, color: "#3a4048", lineHeight: 1.15 }}>An AI agent orders from Valio. <span style={{ color: TEAL_DEEP, fontWeight: 700 }}>The chef decides.</span></div>
        </div>
      </div>
      <div style={{ position: "absolute", left: 150, top: 520, opacity: ease(fr, 26, 36) }}><Label color="#5d6670" size={26}>Built in 48 hours with</Label></div>
      <div style={{ position: "absolute", left: 150, right: 150, top: 568, display: "flex", gap: 28 }}>
        {tools.map((tool, i) => {
          const l = fr - 32 - i * 7;
          return (
            <div key={tool.name} style={{ flex: 1, padding: "30px 34px", borderRadius: 18, background: "#fff", boxShadow: "0 1px 0 rgba(0,0,0,0.04), 0 18px 40px rgba(20,30,40,0.08)", borderTop: `6px solid ${tool.color}`, opacity: ease(l, 0, 9), transform: `translateY(${ease(l, 0, 12, 34, 0)}px)` }}>
              <div style={{ fontSize: 58, fontWeight: 800, letterSpacing: "-0.03em", color: tool.color }}>{tool.name}</div>
              <div style={{ marginTop: 10, fontSize: 30, color: "#4a525b", lineHeight: 1.2 }}>{tool.role}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

/* ---------- 4. live demo ---------- */
function Demo() {
  const fr = useCurrentFrame();
  const t = fr / FPS;
  let idx = 0;
  BEATS.forEach((b, i) => { if (t >= b.t) idx = i; });
  const beat = BEATS[idx];
  const local = (t - beat.t) * FPS;
  const breathe = Math.sin(t * 0.35) * 2.2;
  const enter = ease(fr, 0, 18);
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 42% 45%, #16262d 0%, ${INK} 60%)`, color: "#fff", fontFamily: SANS, overflow: "hidden" }}>
      {/* left: badge and beat tracker */}
      <div style={{ position: "absolute", left: 90, top: 92, opacity: enter }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 12, padding: "10px 18px", borderRadius: 999, background: "rgba(197,225,29,0.12)", border: `2px solid ${LIME}` }}>
          <div style={{ width: 14, height: 14, borderRadius: 999, background: LIME, opacity: 0.55 + 0.45 * Math.abs(Math.sin(t * 3)) }} />
          <span style={{ fontFamily: PIXEL, fontSize: 26, color: LIME }}>LIVE · one take · real time</span>
        </div>
        <div style={{ marginTop: 52, display: "flex", flexDirection: "column", gap: 20 }}>
          {BEATS.map((b, i) => {
            const state = i < idx ? "done" : i === idx ? "now" : "next";
            return (
              <div key={b.n} style={{ display: "flex", alignItems: "center", gap: 16, opacity: state === "next" ? 0.32 : 1 }}>
                <div style={{ width: 18, height: 18, background: state === "now" ? LIME : state === "done" ? TEAL : "transparent", border: state === "next" ? `2px solid ${MUTED}` : "none" }} />
                <span style={{ fontFamily: PIXEL, fontSize: 22, color: state === "now" ? LIME : MUTED }}>{b.n}</span>
                <span style={{ fontSize: 26, fontWeight: state === "now" ? 700 : 500, color: state === "now" ? "#fff" : "#c4cbd2" }}>{b.title}</span>
              </div>
            );
          })}
        </div>
      </div>
      {/* centre: the phone */}
      <div style={{ position: "absolute", left: 760, top: 64, opacity: enter, transform: `translateY(${ease(fr, 0, 20, 60, 0)}px)` }}>
        <IPhone height={880} tilt={breathe} glow={0.8}>
          <Video src={staticFile("demo.mp4")} endAt={f(T.demo.dur)} muted style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", backgroundColor: "#000" }} />
        </IPhone>
      </div>
      {/* right: what is happening now */}
      <div key={beat.n} style={{ position: "absolute", left: 1290, top: 300, width: 540, opacity: ease(local, 0, 8), transform: `translateX(${ease(local, 0, 12, 30, 0)}px)` }}>
        <Label color={LIME} size={30}>{`STEP ${beat.n}`}</Label>
        <div style={{ marginTop: 18, fontSize: 60, fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1.0 }}>{beat.title}</div>
        <div style={{ marginTop: 22, fontSize: 32, color: "#c9d0d6", lineHeight: 1.3 }}>{beat.detail}</div>
      </div>
    </AbsoluteFill>
  );
}

/* ---------- 5. track cards ---------- */
function TrackFrame({ n, name, hero, heroColor, headline, facts, children }: { n: string; name: string; hero: string; heroColor: string; headline: string; facts: string[]; children: React.ReactNode }) {
  const fr = useCurrentFrame();
  const count = interpolate(fr, [4, 26], [0, 1], { ...CLAMP, easing: OUT });
  const heroNum = parseFloat(hero);
  const shown = hero.includes(".") ? (heroNum * count).toFixed(2) : String(Math.round(heroNum * count));
  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${INK_2} 0%, ${INK} 70%)`, color: "#fff", fontFamily: SANS, overflow: "hidden" }}>
      <div style={{ position: "absolute", right: -60, top: -40, opacity: 0.05 }}><DoorGlyph size={1200} color="#fff" /></div>
      <div style={{ position: "absolute", left: 100, top: 96 }}>
        <Label color={MUTED} size={28}>{`${n} / 03 · BUILT WITH`}</Label>
        <div style={{ marginTop: 14, fontSize: 64, fontWeight: 800, letterSpacing: "-0.02em" }}>{name}</div>
      </div>
      <div style={{ position: "absolute", left: 88, top: 290, fontFamily: SANS, fontWeight: 800, fontSize: 250, letterSpacing: "-0.06em", lineHeight: 0.9, color: heroColor }}>{shown}</div>
      <div style={{ position: "absolute", left: 100, top: 560, width: 560, fontSize: 34, fontWeight: 600, lineHeight: 1.22, color: "#e7ebef", opacity: ease(fr, 14, 24) }}>{headline}</div>
      <div style={{ position: "absolute", left: 760, right: 100, top: 110, opacity: ease(fr, 6, 16), transform: `translateY(${ease(fr, 6, 18, 24, 0)}px)` }}>{children}</div>
      <div style={{ position: "absolute", left: 760, right: 100, top: 520, display: "flex", flexDirection: "column", gap: 26 }}>
        {facts.map((fact, i) => {
          const l = fr - 30 - i * 14;
          return (
            <div key={fact} style={{ display: "flex", gap: 20, alignItems: "flex-start", opacity: ease(l, 0, 9), transform: `translateX(${ease(l, 0, 12, 24, 0)}px)` }}>
              <div style={{ flex: "0 0 14px", width: 14, height: 14, marginTop: 14, background: heroColor }} />
              <div style={{ fontSize: 32, lineHeight: 1.28, color: "#dfe4e8" }}>{fact}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

function GeminiCard() {
  const fr = useCurrentFrame();
  const W = 960;
  const pts = [
    { v: 0.115, label: "“coffee milk”", verdict: "asks the chef", color: AMBER, d: 24 },
    { v: 0.897, label: "“lactose-free milk”", verdict: "orders it", color: LIME, d: 36 },
  ];
  return (
    <TrackFrame n="01" name="Gemini" hero="0.70" heroColor={TEAL} headline="The Decisions API scores how sure the agent is. The kitchen sets the bar." facts={[
      "Gemini reads the handwritten Finnish list and talks over the same tools; it never touches money.",
      "Up to 40 assumptions scored in one Decisions call, each a calibrated yes-probability.",
      "0 unsafe auto-orders in 164 chat tests, including 10 injection attempts.",
    ]}>
      <div style={{ position: "relative", width: W, height: 330, borderRadius: 20, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "0" }}>
        <div style={{ position: "absolute", left: 40, top: 30, fontFamily: PIXEL, fontSize: 24, color: MUTED }}>DECISIONS SCORE · p(yes)</div>
        <div style={{ position: "absolute", left: 40, right: 40, top: 168, height: 16, borderRadius: 8, background: `linear-gradient(90deg, rgba(240,168,91,0.35) 0%, rgba(240,168,91,0.35) 70%, rgba(197,225,29,0.45) 70%, rgba(197,225,29,0.45) 100%)` }} />
        <div style={{ position: "absolute", left: 40 + (W - 80) * 0.7 - 2, top: 108, width: 4, height: 96, background: "#fff" }} />
        <div style={{ position: "absolute", left: 40 + (W - 80) * 0.7 - 120, top: 76, width: 240, textAlign: "center", fontFamily: PIXEL, fontSize: 24, color: "#fff" }}>kitchen bar 0.70</div>
        <div style={{ position: "absolute", left: 40, top: 128, fontFamily: PIXEL, fontSize: 22, color: AMBER }}>ASK THE CHEF</div>
        <div style={{ position: "absolute", right: 40, top: 128, fontFamily: PIXEL, fontSize: 22, color: LIME }}>ACT</div>
        {pts.map((p) => {
          const x = 40 + (W - 80) * p.v * ease(fr, p.d, p.d + 16);
          return (
            <div key={p.label} style={{ position: "absolute", left: x - 13, top: 163, opacity: ease(fr, p.d, p.d + 6) }}>
              <div style={{ width: 26, height: 26, borderRadius: 999, background: p.color, boxShadow: `0 0 18px ${p.color}` }} />
              <div style={{ position: "absolute", left: p.v < 0.5 ? -6 : -200, top: 46, width: 230, textAlign: p.v < 0.5 ? "left" : "right", fontSize: 24, lineHeight: 1.25 }}>
                <div style={{ color: "#fff", fontWeight: 700 }}>{p.label} {p.v.toFixed(3)}</div>
                <div style={{ color: p.color }}>{p.verdict}</div>
              </div>
            </div>
          );
        })}
      </div>
    </TrackFrame>
  );
}

const GIT_LOG = [
  "98eca26 Chat: the product the card holds is the product named",
  "afefeb9 Chat: the price the agent quotes is the price ordered",
  "0ee4199 Voice: the reason first, then 'tap Approve'",
  "4ae7920 Allergens: empty Valio record means unknown",
  "8d5ae2d Multi-item: every item gets its own status",
  "e30e676 Decisions score the chef's own words",
  "8d31c67 CRACI: CycloneDX 1.7 dependency graph",
  "7b4656d Assume the next delivery day, held for the chef",
];

function CodexCard() {
  const fr = useCurrentFrame();
  return (
    <TrackFrame n="02" name="Codex" hero="42" heroColor={LIME} headline="commits on main say “Built by Codex”. Claude briefed, reviewed and gated." facts={[
      "Up to 5 Codex workers in parallel, each in its own git worktree, looping against real Gemini.",
      "Codex attacked its own code: it caught a free-from milk passing a peanut ban. Fixed that night.",
      "787 automated tests pass. Every run is logged in docs/CODEX.md.",
    ]}>
      <div style={{ width: 960, height: 330, borderRadius: 20, background: "#0a0d10", border: "1px solid rgba(255,255,255,0.08)", overflow: "hidden" }}>
        <div style={{ display: "flex", gap: 9, padding: "16px 20px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 13, height: 13, borderRadius: 999, background: c }} />)}
          <span style={{ marginLeft: 14, fontFamily: MONO, fontSize: 19, color: MUTED }}>git log --grep="Built by Codex"</span>
        </div>
        <div style={{ padding: "16px 24px", fontFamily: MONO, fontSize: 24, lineHeight: 1.5 }}>
          {GIT_LOG.slice(0, 7).map((line, i) => (
            <div key={line} style={{ whiteSpace: "nowrap", opacity: ease(fr, 6 + i * 4, 12 + i * 4) }}>
              <span style={{ color: LIME }}>{line.slice(0, 7)}</span><span style={{ color: "#cfd6dc" }}>{line.slice(7)}</span>
            </div>
          ))}
        </div>
      </div>
    </TrackFrame>
  );
}

function CraciCard() {
  const fr = useCurrentFrame();
  const chain = ["build 0b4f6c4", "SBOM sha 2d3f2cf6…", "signing key", "signed order"];
  return (
    <TrackFrame n="03" name="CRACI" hero="351" heroColor={TEAL} headline="software parts in this build's SBOM, pulled live from the CRACI API." facts={[
      "All 7 CI jobs run on CRACI runners: CycloneDX SBOM and network trace (19 destinations) per job.",
      "The signing key and every signed order name that build: every order knows which build signed it.",
      "CRACI flagged vulnerabilities at midnight; we upgraded FastAPI, Starlette, cryptography and minimatch that night.",
    ]}>
      <div style={{ width: 960, height: 330, borderRadius: 20, background: "#0a1418", border: "1px solid rgba(76,195,227,0.25)", padding: "26px 30px", boxSizing: "border-box" }}>
        <div style={{ fontFamily: MONO, fontSize: 25, lineHeight: 1.5, color: "#d8f3f8" }}>
          <div style={{ color: MUTED, fontSize: 20 }}>GET /.well-known/front-door-build.json</div>
          <div><span style={{ color: TEAL }}>"status"</span>: <span style={{ color: LIME }}>"ok"</span>,</div>
          <div><span style={{ color: TEAL }}>"component_counts"</span>: {"{ pip: 170, npm: 181 }"},</div>
          <div><span style={{ color: TEAL }}>"network_destinations"</span>: 19,</div>
        </div>
        <div style={{ marginTop: 20, display: "flex", alignItems: "center", gap: 12 }}>
          {chain.map((c, i) => (
            <div key={c} style={{ display: "flex", alignItems: "center", gap: 12, opacity: ease(fr, 20 + i * 8, 28 + i * 8) }}>
              <div style={{ padding: "10px 16px", borderRadius: 10, background: i === 3 ? "rgba(197,225,29,0.15)" : "rgba(76,195,227,0.12)", border: `1px solid ${i === 3 ? LIME : "rgba(76,195,227,0.5)"}`, fontFamily: PIXEL, fontSize: 21, color: i === 3 ? LIME : TEAL, whiteSpace: "nowrap" }}>{c}</div>
              {i < chain.length - 1 ? <div style={{ color: MUTED, fontSize: 24 }}>→</div> : null}
            </div>
          ))}
        </div>
      </div>
    </TrackFrame>
  );
}

/* ---------- sound ---------- */
function Sound() {
  return (
    <>
      <Sequence from={f(T.door.start)} durationInFrames={f(1.4)} layout="none" name="door creak"><Audio src={staticFile("sfx/door-creak.wav")} gainDb={-16} fadeIn={0.01} fadeOut={0.4} /></Sequence>
      <Sequence from={f(T.door.start + 1.1)} durationInFrames={f(1.8)} layout="none" name="door whoosh"><Audio src={staticFile("sfx/door-whoosh.wav")} gainDb={-14} fadeIn={0.03} fadeOut={0.5} /></Sequence>
      {[T.gemini.start, T.codex.start, T.craci.start].map((s) => <Sequence key={s} from={f(s + 0.15)} durationInFrames={f(0.8)} layout="none" name="card hit"><Audio src={staticFile("sfx/stamp-hit.wav")} gainDb={-22} fadeIn={0.01} fadeOut={0.3} /></Sequence>)}
    </>
  );
}

function Film() {
  const seq = (k: keyof typeof T, el: React.ReactNode) => <Sequence from={f(T[k].start)} durationInFrames={f(T[k].dur)} name={k}>{el}</Sequence>;
  return (
    <AbsoluteFill style={{ background: INK }}>
      <style>{FONTS}</style>
      {seq("shot", <ColdShot />)}
      {seq("insert", <ColdInsert />)}
      {seq("door", <DoorTransition durationInFrames={f(T.door.dur)} />)}
      {seq("title", <TitleCard />)}
      {seq("demo", <Demo />)}
      {seq("gemini", <GeminiCard />)}
      {seq("codex", <CodexCard />)}
      {seq("craci", <CraciCard />)}
      {seq("closer", <Closer durationInFrames={f(T.closer.dur)} />)}
      <Sound />
      <Captions />
      <Mix lufs={-14} ceiling={-1.5} />
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="front-door-film" component={Film} width={1920} height={1080} fps={FPS} durationInFrames={f(TOTAL)} />);
