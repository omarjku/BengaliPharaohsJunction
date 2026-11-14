// Front Door: the Junction 2026 submission video (T22). Shot list: docs/VIDEO.md. 1:55 at 30 fps, 1920x1080.
// Screens are real recordings of the app (video/record.mjs), cut to their slots by video/cut.sh.
// Voiceover: drop the recorded take at media/vo.wav and set HAS_VO = true; the script and its timings are in
// vo-script.md (one line per shot, the same SHOTS below). No synthetic voice is generated here.
import { AbsoluteFill, Audio, Composition, Sequence, Video, interpolate, registerRoot, staticFile, useCurrentFrame } from "raea";

const FPS = 30;
const HAS_VO = false;

// The app's own palette (frontend/src/index.css): warm paper, ink, one blue accent; amber and green only as status.
const C = { paper: "#f9f8f5", ink: "#1c1f23", ink2: "#5d6670", line: "#e7e9ec", accent: "#0b5cad", good: "#1e7a3c", warn: "#8a5a00" };
const FONT = "SF Pro Display, -apple-system, Helvetica Neue, Arial, sans-serif";

type Shot =
  | { kind: "desk" | "phone"; clip: string; s: number; caption: string; kicker?: string }
  | { kind: "card"; s: number; card: () => JSX.Element };

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const fadeIn = (f: number, at = 0, len = 10) => interpolate(f, [at, at + len], [0, 1], clamp);
const rise = (f: number, at = 0) => interpolate(f, [at, at + 14], [24, 0], clamp);

function Kicker({ text }: { text: string }) {
  return <div style={{ fontSize: 34, color: C.ink2, letterSpacing: 0.2, marginBottom: 18 }}>{text}</div>;
}

/** The shot's one line, set in the app's answer style. */
function Caption({ text, kicker, width }: { text: string; kicker?: string; width: number }) {
  const f = useCurrentFrame();
  return (
    <div style={{ width, opacity: fadeIn(f, 6), transform: `translateY(${rise(f, 6)}px)` }}>
      {kicker && <Kicker text={kicker} />}
      <div style={{ fontFamily: FONT, fontSize: 76, fontWeight: 650, lineHeight: 1.08, letterSpacing: -1.2, color: C.ink }}>{text}</div>
    </div>
  );
}

/** A desktop recording in a quiet frame, with a slow push so it never stands still. */
function Desk({ clip, caption, kicker, frames }: { clip: string; caption: string; kicker?: string; frames: number }) {
  const f = useCurrentFrame();
  const z = interpolate(f, [0, frames], [1, 1.035], clamp);
  return (
    <AbsoluteFill style={{ background: C.paper, flexDirection: "row", alignItems: "center", padding: "0 96px", gap: 72 }}>
      <div style={{ width: 1088, height: 680, borderRadius: 20, overflow: "hidden", border: `1px solid ${C.line}`, background: "#fff", flex: "none" }}>
        <Video src={staticFile(`${clip}.mp4`)} muted style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 0%", transform: `scale(${z})`, transformOrigin: "50% 0%" }} />
      </div>
      <Caption text={caption} kicker={kicker} width={560} />
    </AbsoluteFill>
  );
}

/** A phone recording, upright, beside its line. */
function Phone({ clip, caption, kicker }: { clip: string; caption: string; kicker?: string }) {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.paper, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 120, transform: drift(f) }}>
      <div style={{ width: 444, height: 960, borderRadius: 44, overflow: "hidden", border: `10px solid ${C.ink}`, background: "#fff", flex: "none" }}>
        <Video src={staticFile(`${clip}.mp4`)} muted style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 0%" }} />
      </div>
      <Caption text={caption} kicker={kicker} width={760} />
    </AbsoluteFill>
  );
}

/** A slow, steady push (about 3% over 10 s), so a card or a phone shot never stands still. */
const drift = (f: number) => `scale(${interpolate(f, [0, 300], [1, 1.03], clamp)})`;

function CardShell({ children }: { children: JSX.Element | JSX.Element[] }) {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.paper }}>
      <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center", fontFamily: FONT, color: C.ink, transform: drift(f), transformOrigin: "30% 50%" }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
}

function Problem() {
  const f = useCurrentFrame();
  return (
    <CardShell>
      <div style={{ opacity: fadeIn(f), transform: `translateY(${rise(f)}px)` }}>
        <div style={{ fontSize: 220, fontWeight: 700, letterSpacing: -6, lineHeight: 1 }}>90%</div>
        <div style={{ fontSize: 60, color: C.ink2, marginTop: 12 }}>of B2B buying via AI agents by 2028</div>
      </div>
      <div style={{ fontSize: 64, fontWeight: 600, marginTop: 72, opacity: fadeIn(f, 90), transform: `translateY(${rise(f, 90)}px)` }}>
        Valio Aimo has A.I.mo. Buyers will bring their own agents.
      </div>
      <div style={{ position: "absolute", left: 160, bottom: 120, fontSize: 28, color: C.ink2 }}>Gartner, via Digital Commerce 360 (Nov 2025)</div>
    </CardShell>
  );
}

function Answer() {
  const f = useCurrentFrame();
  const box = (t: string, door = false, at = 0) => (
    <div style={{ padding: "26px 40px", borderRadius: 18, fontSize: 46, fontWeight: 600, border: door ? `3px solid ${C.accent}` : `2px solid ${C.line}`,
      color: door ? C.accent : C.ink, background: "#fff", opacity: fadeIn(f, at), transform: `translateY(${rise(f, at)}px)` }}>{t}</div>
  );
  return (
    <CardShell>
      <div style={{ fontSize: 34, color: C.ink2, marginBottom: 28 }}>Front Door</div>
      <div style={{ fontSize: 96, fontWeight: 700, letterSpacing: -2.4, lineHeight: 1.05, maxWidth: 1500, opacity: fadeIn(f) }}>
        The buyer's agent is the visitor, and Valio wants a front door.
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 28, marginTop: 80, fontSize: 46, color: C.ink2 }}>
        {box("Any buyer's agent", false, 40)}<span style={{ opacity: fadeIn(f, 55) }}>→</span>{box("Valio front door", true, 60)}<span style={{ opacity: fadeIn(f, 75) }}>→</span>{box("Valio", false, 80)}
      </div>
    </CardShell>
  );
}

function Trust() {
  const f = useCurrentFrame();
  const row = (t: string, sub: string, at: number) => (
    <div style={{ opacity: fadeIn(f, at), transform: `translateY(${rise(f, at)}px)`, marginBottom: 44 }}>
      <div style={{ fontSize: 72, fontWeight: 650, letterSpacing: -1.2 }}>{t}</div>
      <div style={{ fontSize: 38, color: C.ink2, marginTop: 6 }}>{sub}</div>
    </div>
  );
  return (
    <CardShell>
      <div style={{ fontSize: 34, color: C.ink2, marginBottom: 48 }}>The trust layer</div>
      {row("Every decision signed", "Ed25519, checkable at /.well-known/front-door-keys.json", 0)}
      {row("Audited for the buyer and for Valio", "every order, hold, refusal and sign-off", 30)}
      {row("Any agent can plug in", "OpenAPI 3.1, JSON Schemas, an MCP server, optional RFC 9421 signing", 60)}
    </CardShell>
  );
}

function Gemini() {
  const f = useCurrentFrame();
  const rows = [["0.6", "15", "0"], ["0.7", "14", "0"], ["0.8", "12", "0"]];
  return (
    <CardShell>
      <div style={{ fontSize: 34, color: C.ink2, marginBottom: 36 }}>Gemini Decisions: calibrated confidence decides when the agent acts alone</div>
      <div style={{ display: "flex", gap: 140, alignItems: "flex-start" }}>
        <div style={{ fontSize: 52 }}>
          <div style={{ display: "flex", gap: 64, fontSize: 30, color: C.ink2, marginBottom: 16 }}><span style={{ width: 120 }}>threshold</span><span style={{ width: 220 }}>handled alone</span><span>wrong orders</span></div>
          {rows.map(([t, h, w], i) => (
            <div key={t} style={{ display: "flex", gap: 64, padding: "14px 0", borderTop: `1px solid ${C.line}`, color: t === "0.7" ? C.accent : C.ink, fontWeight: t === "0.7" ? 700 : 400, opacity: fadeIn(f, 10 + i * 8) }}>
              <span style={{ width: 120 }}>{t}</span><span style={{ width: 220 }}>{h}</span><span>{w}</span>
            </div>
          ))}
          <div style={{ fontSize: 30, color: C.ink2, marginTop: 20 }}>30 hand-labelled cases, real Valio products</div>
        </div>
        <div style={{ maxWidth: 640, opacity: fadeIn(f, 60), transform: `translateY(${rise(f, 60)}px)` }}>
          <div style={{ fontSize: 30, color: C.ink2 }}>Caught by our own QA</div>
          <div style={{ fontSize: 60, fontWeight: 650, lineHeight: 1.1, marginTop: 12 }}>Coffee milk for "milk": now a labelled trap.</div>
        </div>
      </div>
    </CardShell>
  );
}

function Codex() {
  const f = useCurrentFrame();
  const stat = (n: string, l: string, at: number, accent = false) => (
    <div style={{ opacity: fadeIn(f, at), transform: `translateY(${rise(f, at)}px)` }}>
      <div style={{ fontSize: 200, fontWeight: 700, letterSpacing: -6, lineHeight: 1, color: accent ? C.accent : C.ink }}>{n}</div>
      <div style={{ fontSize: 40, color: C.ink2, marginTop: 8 }}>{l}</div>
    </div>
  );
  return (
    <CardShell>
      <div style={{ fontSize: 34, color: C.ink2, marginBottom: 40 }}>Codex as our adversary</div>
      <div style={{ display: "flex", gap: 140 }}>{stat("9", "reviews", 0)}{stat("62", "findings", 10)}{stat("43", "fixed, each with a test", 20, true)}</div>
    </CardShell>
  );
}

function Close() {
  const f = useCurrentFrame();
  return (
    <CardShell>
      <div style={{ fontSize: 96, fontWeight: 700, letterSpacing: -2.4, lineHeight: 1.05, opacity: fadeIn(f) }}>Any agent can visit.<br />Only the right orders get in.</div>
      <div style={{ fontSize: 44, color: C.ink2, marginTop: 64, opacity: fadeIn(f, 20) }}>Front Door · built at Junction 2026 · Omar Kassem, Fathia Fairuz Zoha</div>
      <div style={{ fontSize: 44, color: C.accent, marginTop: 16, opacity: fadeIn(f, 20) }}>github.com/omarjku/BengaliPharaohsJunction</div>
    </CardShell>
  );
}

/** One line per shot; the VO script (vo-script.md) follows the same order and seconds. */
export const SHOTS: Shot[] = [
  { kind: "desk", clip: "hook", s: 5, kicker: "An order with a planted instruction", caption: "Flagged. Nothing ordered." },
  { kind: "card", s: 8, card: Problem },
  { kind: "card", s: 7, card: Answer },
  { kind: "desk", clip: "finnish", s: 10, kicker: "In Finnish", caption: "Sure, and within the limits: ordered by itself. €156." },
  { kind: "phone", clip: "voice", s: 10, kicker: "By voice, mid-service", caption: "Text in about a second. Ordered before the cut-off." },
  { kind: "desk", clip: "held", s: 9, kicker: "1000 L of lactose-free milk", caption: "€60 over the chef's limit. The door holds it." },
  { kind: "phone", clip: "approve", s: 8, kicker: "The agent's key can't approve", caption: "The chef can, from a phone." },
  { kind: "desk", clip: "sugar", s: 6, kicker: "Judgment", caption: "Caster sugar for baking, not 5 g sachets." },
  { kind: "desk", clip: "menu", s: 10, kicker: "A menu for 80 guests", caption: "A cart with every assumption shown. It always asks." },
  { kind: "phone", clip: "urgent", s: 8, kicker: "Helsinki, as soon as possible", caption: "Cash & Carry or Click & Collect: suggested, never ordered." },
  { kind: "desk", clip: "history", s: 4, kicker: "History", caption: "What was ordered, held or refused." },
  { kind: "desk", clip: "rules", s: 4, kicker: "Rules", caption: "In the chef's own words." },
  { kind: "card", s: 8, card: Trust },
  { kind: "card", s: 7, card: Gemini },
  { kind: "card", s: 5, card: Codex },
  { kind: "card", s: 6, card: Close },
];
const TOTAL = SHOTS.reduce((n, s) => n + s.s * FPS, 0);

function Piece() {
  let from = 0;
  return (
    <AbsoluteFill style={{ background: C.paper, fontFamily: FONT }}>
      {SHOTS.map((shot, i) => {
        const frames = shot.s * FPS;
        const at = from;
        from += frames;
        return (
          <Sequence key={i} from={at} durationInFrames={frames} name={shot.kind === "card" ? `card ${i}` : shot.clip}>
            {shot.kind === "card" ? <shot.card /> : shot.kind === "desk"
              ? <Desk clip={shot.clip} caption={shot.caption} kicker={shot.kicker} frames={frames} />
              : <Phone clip={shot.clip} caption={shot.caption} kicker={shot.kicker} />}
          </Sequence>
        );
      })}
      {HAS_VO && <Audio src={staticFile("vo.wav")} />}
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="front-door" width={1920} height={1080} fps={FPS} durationInFrames={TOTAL} component={Piece} />);
