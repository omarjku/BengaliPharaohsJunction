import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ArchitectureStrip } from "./components/ArchitectureStrip";
import { ConfidenceBar } from "./components/ConfidenceBar";
import { DoorGlyph } from "./components/DoorGlyph";
import { EndCard } from "./components/EndCard";
import { EvidenceCards } from "./components/EvidenceCards";
import { Arrow, Check, Spinner } from "./components/Icons";
import { LiveBadge } from "./components/LiveBadge";
import { Stamp } from "./components/Stamp";
import { TicketCard } from "./components/TicketCard";
import { TrapTickets } from "./components/TrapTickets";
import { VideoSlot } from "./components/VideoSlot";
import { FPS } from "./config";
import { clamp, enter, progress } from "./anim";
import { C } from "./tokens";
import { Beat, Overlay } from "./types";

type K<T extends Overlay["kind"]> = Extract<Overlay, { kind: T }>;

/* ---------- stages ---------- */

/** Light stage for beats with no phone: content is centred above the caption zone. */
const FullStage: React.FC<{ children: React.ReactNode; gap?: number }> = ({ children, gap = 40 }) => (
  <AbsoluteFill style={{ background: C.wash }}>
    <div
      style={{
        position: "absolute",
        inset: "0 0 190px 0",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap,
      }}
    >
      {children}
    </div>
  </AbsoluteFill>
);

/** Phone on the left (screen recording or placeholder), explainer on the right. */
const PhoneStage: React.FC<{ beat: Beat; children: React.ReactNode }> = ({ beat, children }) => {
  const m = beat.mediaSlot;
  return (
    <AbsoluteFill style={{ background: C.wash }}>
      {m && (
        <div style={{ position: "absolute", left: 140, top: 36 }}>
          <VideoSlot src={m.src} name={m.label} startFrom={Math.round((m.startFromSec ?? 0) * FPS)} variant="phone" />
        </div>
      )}
      <div
        style={{
          position: "absolute",
          left: 640,
          top: 36,
          width: 1140,
          height: 830,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 34,
        }}
      >
        <LiveBadge style={{ position: "absolute", top: 0, left: 0 }} />
        {children}
      </div>
    </AbsoluteFill>
  );
};

const Pill: React.FC<{ children: React.ReactNode; fg?: string; bg?: string; size?: number; style?: React.CSSProperties }> = ({
  children,
  fg = C.ink,
  bg = C.paper,
  size = 36,
  style,
}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 14,
      color: fg,
      background: bg,
      border: `3px solid ${fg}`,
      borderRadius: 999,
      fontSize: size,
      fontWeight: 900,
      letterSpacing: "0.07em",
      padding: "10px 28px",
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </div>
);

const Row: React.FC<{ k: string; v: string; big?: boolean; color?: string }> = ({ k, v, big, color = C.ink }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 24, padding: "8px 0" }}>
    <span style={{ fontSize: big ? 38 : 32, fontWeight: 700, letterSpacing: "0.05em", color: C.mute }}>{k}</span>
    <span style={{ fontSize: big ? 76 : 44, fontWeight: 900, color, fontVariantNumeric: "tabular-nums" }}>{v}</span>
  </div>
);

/* ---------- beat 01: night-kitchen opening ---------- */

const Opening: React.FC<{ beat: Beat; o: K<"opening"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  const m = beat.mediaSlot!;
  const sweep = interpolate(frame, [0, 180], [18, 34], clamp);
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      {/* cold blue kitchen light */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(1100px 760px at ${sweep}% 30%, rgba(70,150,240,0.42), transparent 70%), linear-gradient(180deg, rgba(11,58,110,0.35), rgba(28,31,35,0) 55%)`,
        }}
      />
      <VideoSlot src={m.src} name={m.label} variant="bleed" />
      {/* legibility veil over footage */}
      <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(28,31,35,0.78) 0%, rgba(28,31,35,0.35) 60%, rgba(28,31,35,0.1) 100%)" }} />
      <div
        style={{
          position: "absolute",
          right: 56,
          top: 48,
          fontSize: 28,
          fontWeight: 500,
          color: "#C9D3DE",
          background: "rgba(28,31,35,0.7)",
          border: "1px solid rgba(255,255,255,0.18)",
          borderRadius: 10,
          padding: "6px 16px",
        }}
      >
        {o.tag}
      </div>
      <div style={{ position: "absolute", left: 140, top: 270, width: 1700 }}>
        <div
          style={{
            fontSize: 112,
            whiteSpace: "nowrap",
            fontWeight: 900,
            color: C.paper,
            letterSpacing: "0.01em",
            lineHeight: 1.05,
            textShadow: "0 0 50px rgba(80,160,255,0.55)",
            ...enter(frame, 8, 20, 30),
          }}
        >
          {o.clock}
        </div>
        <div
          style={{
            marginTop: 40,
            width: 1200,
            fontSize: 62,
            fontWeight: 700,
            color: "#8EC0FF",
            letterSpacing: "0.03em",
            lineHeight: 1.18,
            ...enter(frame, 40, 20, 24),
          }}
        >
          {o.question}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ---------- beat 02 ---------- */

const Intake: React.FC<{ beat: Beat; o: K<"intake"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  return (
    <PhoneStage beat={beat}>
      <TicketCard title={o.heading} width={760} tilt={-1.2} at={6}>
        <div style={{ fontSize: 96, fontWeight: 900, lineHeight: 1.05 }}>{o.big}</div>
        <div style={{ fontSize: 44, fontWeight: 700, color: C.blue, letterSpacing: "0.06em", marginTop: 6 }}>{o.sub}</div>
      </TicketCard>
      <div style={{ display: "flex", gap: 20 }}>
        {o.chips.map((c, i) => (
          <div key={c} style={enter(frame, 40 + i * 24, 14, 16)}>
            <Pill fg={i === 0 ? C.ink : C.blue} bg={i === 0 ? C.paper : "#E6F0FA"} size={30}>
              {i === 1 && <DoorGlyph height={30} color={C.blue} />}
              {c}
            </Pill>
          </div>
        ))}
      </div>
    </PhoneStage>
  );
};

/* ---------- beat 03 ---------- */

const scribble = (i: number, w: number) => {
  // a wobbly handwriting line, different per row
  const y = 16;
  const segs = 9 + (i % 3);
  const step = w / segs;
  let d = `M0 ${y}`;
  for (let s = 0; s < segs; s++) {
    const a = ((s * 7 + i * 5) % 9) - 4;
    d += ` q${step / 2} ${-14 + a} ${step} ${a / 2}`;
  }
  return d;
};

const Reads: React.FC<{ beat: Beat; o: K<"reads"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  const rows = Array.from({ length: o.lines });
  const lineW = [420, 380, 440, 360, 410, 300, 390];
  return (
    <PhoneStage beat={beat}>
      <div style={{ display: "flex", gap: 44, alignItems: "center" }}>
        <TicketCard title={o.header} width={560} tilt={-1} at={4}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((_, i) => {
              const p = progress(frame, 14 + i * 9, 14);
              const w = lineW[i % lineW.length];
              return (
                <svg key={i} width={w + 10} height={36} style={{ display: "block" }}>
                  <path
                    d={scribble(i, w)}
                    pathLength={1}
                    strokeDasharray={1}
                    strokeDashoffset={1 - p}
                    fill="none"
                    stroke={C.ink}
                    strokeWidth={4}
                    strokeLinecap="round"
                  />
                </svg>
              );
            })}
          </div>
        </TicketCard>
        <div style={{ position: "relative", width: 440 }}>
          <div
            style={{
              background: C.amberBg,
              border: `3px solid ${C.amber}`,
              borderRadius: 8,
              padding: "26px 30px 34px",
              transform: `rotate(2.5deg) translateX(${(1 - progress(frame, 96, 16)) * 60}px)`,
              opacity: progress(frame, 96, 16),
              boxShadow: "0 14px 24px rgba(28,31,35,0.16)",
            }}
          >
            <div style={{ fontSize: 24, fontWeight: 900, letterSpacing: "0.12em", color: C.amber, marginBottom: 12 }}>PLANTED NOTE</div>
            <div style={{ fontSize: 40, fontWeight: 500, lineHeight: 1.25, color: C.ink }}>“{o.planted}”</div>
          </div>
          <div style={{ position: "absolute", left: 20, bottom: -52 }}>
            <Stamp label={o.stamp} tone="red" size={64} at={132} rotate={-9} />
          </div>
        </div>
      </div>
      <div style={{ marginTop: 40, ...enter(frame, 168, 14, 16) }}>
        <Pill fg={C.green} bg={C.greenBg} size={34}>
          <Check size={34} />
          {o.note}
        </Pill>
      </div>
    </PhoneStage>
  );
};

/* ---------- beat 04 ---------- */

const Checks: React.FC<{ beat: Beat; o: K<"checks"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  return (
    <PhoneStage beat={beat}>
      <div style={{ display: "flex", flexDirection: "column", gap: 18, width: 820 }}>
        {o.chips.map((c, i) => {
          const start = 10 + i * 30;
          const done = frame >= start + 20;
          return (
            <div
              key={c}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                height: 96,
                padding: "0 34px",
                borderRadius: 20,
                background: done ? C.greenBg : C.paper,
                border: `4px solid ${done ? C.green : C.line}`,
                color: done ? C.green : C.ink,
                fontSize: 46,
                fontWeight: 900,
                letterSpacing: "0.06em",
                ...enter(frame, start - 6, 12, 20),
              }}
            >
              <span>{c}</span>
              {done ? <Check size={52} /> : <Spinner size={44} frame={frame} />}
            </div>
          );
        })}
      </div>
    </PhoneStage>
  );
};

/* ---------- beat 05 ---------- */

const Held: React.FC<{ beat: Beat; o: K<"held"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  const W = 780;
  const scale = o.amount * 1.12; // gauge max
  const limitX = (o.limitAmount / scale) * 100;
  const fill = progress(frame, 24, 40) * (o.amount / scale) * 100;
  return (
    <PhoneStage beat={beat}>
      <div style={{ position: "relative" }}>
        <TicketCard title="PROPOSED ORDER" width={W} tilt={-0.8} at={4}>
          <Row k={o.qty} v={o.item} big={false} />
          <div style={{ fontSize: 100, fontWeight: 900, textAlign: "right", color: C.amber, lineHeight: 1.1 }}>{o.price}</div>
          <div style={{ position: "relative", height: 40, borderRadius: 12, background: "#E1E5EA", margin: "20px 0 14px" }}>
            <div style={{ width: `${Math.min(fill, limitX)}%`, height: "100%", background: C.green, borderRadius: "12px 0 0 12px" }} />
            <div
              style={{
                position: "absolute",
                left: `${limitX}%`,
                top: 0,
                width: `${Math.max(0, fill - limitX)}%`,
                height: "100%",
                background: C.amber,
                borderRadius: "0 12px 12px 0",
              }}
            />
            <div style={{ position: "absolute", left: `${limitX}%`, top: -10, bottom: -10, borderLeft: `5px dashed ${C.ink}` }} />
          </div>
          <Row k={o.limitLabel} v={o.limit} color={C.ink} />
        </TicketCard>
        <div style={{ position: "absolute", left: 40, top: 172 }}>
          <Stamp label={o.stamp} tone="amber" size={68} at={96} rotate={-8} />
        </div>
      </div>
    </PhoneStage>
  );
};

/* ---------- beat 06 ---------- */

const ConfStrip: React.FC<{ beat: Beat; o: K<"confidence-strip"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  return (
    <PhoneStage beat={beat}>
      <div style={{ background: C.paper, borderRadius: 28, padding: "20px 44px 30px", boxShadow: "0 16px 30px rgba(28,31,35,0.1)" }}>
        <ConfidenceBar scores={o.scores} threshold={o.threshold} width={920} at={6} />
      </div>
      <div style={{ fontSize: 34, fontWeight: 900, letterSpacing: "0.07em", color: C.red, ...enter(frame, 90, 14, 16) }}>{o.note}</div>
    </PhoneStage>
  );
};

/* ---------- beat 07 ---------- */

const CannotApprove: React.FC<{ beat: Beat; o: K<"cannot-approve"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  return (
    <PhoneStage beat={beat}>
      <div style={{ position: "relative", paddingBottom: 50 }}>
        <TicketCard title="HELD" width={700} tilt={-0.8} at={2}>
          <Row k={o.item} v={o.price} />
        </TicketCard>
        <div style={{ position: "absolute", left: -40, bottom: -10 }}>
          <Stamp label={o.stamp} tone="red" size={58} at={44} rotate={-6} />
        </div>
      </div>
      <div style={{ textAlign: "center", marginTop: 40 }}>
        <div style={{ fontSize: 52, fontWeight: 900, letterSpacing: "0.04em", ...enter(frame, 100, 14, 16) }}>{o.lines[0]}</div>
        <div style={{ fontSize: 76, fontWeight: 900, color: C.blue, marginTop: 8, letterSpacing: "0.04em", ...enter(frame, 130, 14, 16) }}>
          {o.lines[1]}
        </div>
      </div>
    </PhoneStage>
  );
};

/* ---------- beat 08 ---------- */

const Ordered: React.FC<{ beat: Beat; o: K<"ordered"> }> = ({ beat, o }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const press = spring({ frame: frame - 36, fps, config: { damping: 8, stiffness: 300 } });
  const btnScale = frame < 36 ? 1 : 1 - 0.1 * Math.sin(Math.min(1, press) * Math.PI);
  return (
    <PhoneStage beat={beat}>
      <div style={{ position: "relative", paddingBottom: 30 }}>
        <TicketCard title="ORDER" width={700} tilt={-0.6} at={2}>
          <Row k={o.item} v={o.price} />
          <div style={{ height: 130 }} />
        </TicketCard>
        <div style={{ position: "absolute", right: 40, bottom: 56 }}>
          <Stamp label={o.heldStamp} tone="amber" size={72} at={6} exitAt={70} rotate={-7} />
        </div>
        <div style={{ position: "absolute", right: 10, bottom: 40 }}>
          <Stamp label={o.stamp} tone="green" size={84} at={74} rotate={-8} />
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 14 }}>
        <div
          style={{
            background: C.blue,
            color: C.paper,
            fontSize: 44,
            fontWeight: 900,
            letterSpacing: "0.08em",
            padding: "16px 54px",
            borderRadius: 18,
            transform: `scale(${btnScale})`,
            boxShadow: "0 10px 20px rgba(11,92,173,0.35)",
            ...enter(frame, 14, 12, 14),
          }}
        >
          {o.button}
        </div>
        {o.chips.map((c, i) => (
          <div key={c} style={enter(frame, 116 + i * 16, 14, 16)}>
            <Pill fg={C.green} bg={C.greenBg} size={34}>
              <Check size={34} />
              {c}
            </Pill>
          </div>
        ))}
      </div>
    </PhoneStage>
  );
};

/* ---------- beat 09 ---------- */

const Verify: React.FC<{ o: K<"verify"> }> = ({ o }) => {
  const frame = useCurrentFrame();
  return (
    <FullStage gap={70}>
      <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
        <Check size={110} />
        <Stamp label={o.stamp} tone="green" size={104} at={8} rotate={-3} />
      </div>
      <div style={{ opacity: progress(frame, 36, 10) }}>
        <ArchitectureStrip steps={o.steps} at={36} />
      </div>
    </FullStage>
  );
};

/* ---------- beat 10 ---------- */

const Threshold: React.FC<{ o: K<"threshold"> }> = ({ o }) => {
  const frame = useCurrentFrame();
  return (
    <FullStage gap={34}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 58, fontWeight: 700, color: C.mute, letterSpacing: "0.06em", ...enter(frame, 0, 14, 16) }}>{o.lead}</div>
        <div style={{ fontSize: 88, fontWeight: 900, color: C.ink, letterSpacing: "0.03em", marginTop: 4, ...enter(frame, 20, 14, 16) }}>
          {o.headline}
        </div>
      </div>
      <div style={{ background: C.paper, borderRadius: 28, padding: "10px 60px 30px", boxShadow: "0 16px 30px rgba(28,31,35,0.1)" }}>
        <ConfidenceBar scores={o.scores} threshold={o.threshold} width={1500} at={40} big zoneLeft={o.zoneLeft} zoneRight={o.zoneRight} />
      </div>
    </FullStage>
  );
};

/* ---------- beat 11 / 12 ---------- */

const Evidence: React.FC<{ o: K<"evidence"> }> = ({ o }) => (
  <FullStage>
    <EvidenceCards items={o.items} note={o.note} at={14} interval={54} />
  </FullStage>
);

const Traps: React.FC<{ o: K<"traps"> }> = ({ o }) => (
  <FullStage>
    <TrapTickets items={o.items} at={10} interval={50} />
  </FullStage>
);

/* ---------- beat 13 ---------- */

const Fallback: React.FC<{ o: K<"fallback"> }> = ({ o }) => {
  const frame = useCurrentFrame();
  return (
    <FullStage gap={56}>
      <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
        <div style={{ ...enter(frame, 4, 14, 24), position: "relative" }}>
          <div
            style={{
              width: 680,
              height: 250,
              boxSizing: "border-box",
              borderRadius: 24,
              border: `4px dashed ${C.mute}`,
              background: C.paper,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
              fontSize: 46,
              fontWeight: 900,
              letterSpacing: "0.05em",
              color: C.mute,
            }}
          >
            {o.left}
            <Pill fg={C.amber} bg={C.amberBg} size={28}>
              {o.leftBadge}
            </Pill>
          </div>
        </div>
        <div style={{ opacity: progress(frame, 30, 12) }}>
          <Arrow size={64} length={150} color={C.ink} />
        </div>
        <div style={{ ...enter(frame, 40, 14, 24) }}>
          <div
            style={{
              width: 680,
              height: 250,
              boxSizing: "border-box",
              borderRadius: 24,
              background: C.blue,
              color: C.paper,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 26,
              fontSize: 46,
              fontWeight: 900,
              letterSpacing: "0.05em",
              boxShadow: "0 18px 30px rgba(11,92,173,0.3)",
            }}
          >
            <DoorGlyph height={110} color={C.paper} />
            <span style={{ width: 380, lineHeight: 1.12 }}>{o.right}</span>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 28 }}>
        <div style={enter(frame, 90, 14, 16)}>
          <Pill fg={C.amber} bg={C.amberBg} size={42}>{o.tags[0]}</Pill>
        </div>
        <div style={enter(frame, 114, 14, 16)}>
          <Pill fg={C.green} bg={C.greenBg} size={42}>
            <Check size={42} />
            {o.tags[1]}
          </Pill>
        </div>
      </div>
    </FullStage>
  );
};

/* ---------- beat 14 ---------- */

const OtherAgent: React.FC<{ o: K<"other-agent"> }> = ({ o }) => {
  const frame = useCurrentFrame();
  const [a, m, d] = o.nodes;
  const box: React.CSSProperties = {
    height: 250,
    boxSizing: "border-box",
    borderRadius: 24,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 46,
    fontWeight: 900,
    letterSpacing: "0.05em",
  };
  return (
    <FullStage gap={54}>
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        <div style={{ ...box, width: 520, background: C.paper, border: `4px solid ${C.line}`, gap: 22, ...enter(frame, 4, 14, 24) }}>
          <svg width="76" height="76" viewBox="0 0 76 76">
            <rect x="10" y="18" width="56" height="44" rx="12" fill="none" stroke={C.ink} strokeWidth="5" />
            <circle cx="28" cy="40" r="5" fill={C.ink} />
            <circle cx="48" cy="40" r="5" fill={C.ink} />
            <path d="M38 18V8" stroke={C.ink} strokeWidth="5" strokeLinecap="round" />
          </svg>
          <span style={{ width: 280, lineHeight: 1.1 }}>{a}</span>
        </div>
        <div style={{ opacity: progress(frame, 24, 12) }}>
          <Arrow size={56} length={90} />
        </div>
        <div style={{ ...box, width: 240, background: "#E6F0FA", color: C.blue, border: `4px solid ${C.blue}`, ...enter(frame, 34, 14, 24) }}>{m}</div>
        <div style={{ opacity: progress(frame, 54, 12) }}>
          <Arrow size={56} length={90} />
        </div>
        <div style={{ ...box, width: 560, background: C.blue, color: C.paper, gap: 24, boxShadow: "0 18px 30px rgba(11,92,173,0.3)", ...enter(frame, 64, 14, 24) }}>
          <DoorGlyph height={110} color={C.paper} />
          <span style={{ width: 280, lineHeight: 1.1 }}>{d}</span>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 22, ...enter(frame, 110, 14, 16) }}>
        <span style={{ fontSize: 36, fontWeight: 900, letterSpacing: "0.1em", color: C.mute }}>{o.verifyLabel}</span>
        {o.verifies.map((v) => (
          <Pill key={v} fg={C.green} bg={C.greenBg} size={36}>
            <Check size={36} />
            {v}
          </Pill>
        ))}
      </div>
    </FullStage>
  );
};

/* ---------- beat 15 ---------- */

const Codex: React.FC<{ o: K<"codex"> }> = ({ o }) => {
  const frame = useCurrentFrame();
  const n = Math.round(o.count * progress(frame, 10, 60));
  const rows = 6;
  return (
    <AbsoluteFill style={{ background: C.wash }}>
      <div style={{ position: "absolute", left: 150, top: 150, width: 900 }}>
        <div style={{ fontSize: 400, fontWeight: 900, color: C.blue, lineHeight: 0.95, fontVariantNumeric: "tabular-nums" }}>{n}</div>
        <div style={{ fontSize: 60, fontWeight: 900, letterSpacing: "0.05em", lineHeight: 1.12, marginTop: 20, color: C.ink, ...enter(frame, 40, 16, 20) }}>
          {o.text}
        </div>
      </div>
      <div style={{ position: "absolute", left: 1100, top: 130, width: 660, display: "flex", flexDirection: "column", gap: 20 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              background: C.paper,
              border: `3px solid ${C.line}`,
              borderRadius: 16,
              padding: "20px 26px",
              ...enter(frame, 16 + i * 9, 12, 30),
            }}
          >
            <div style={{ width: 22, height: 22, borderRadius: 11, background: C.blue, flex: "none" }} />
            <div style={{ height: 14, borderRadius: 7, background: "#DDE2E8", width: 150 + ((i * 53) % 110) }} />
            <div style={{ marginLeft: "auto", fontSize: 28, fontWeight: 700, color: C.blue, letterSpacing: "0.04em", whiteSpace: "nowrap" }}>
              Built by Codex
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ---------- dispatcher ---------- */

export const Scene: React.FC<{ beat: Beat }> = ({ beat }) => {
  const o = beat.overlay;
  if (!o) return <AbsoluteFill style={{ background: C.wash }} />;
  switch (o.kind) {
    case "opening":
      return <Opening beat={beat} o={o} />;
    case "intake":
      return <Intake beat={beat} o={o} />;
    case "reads":
      return <Reads beat={beat} o={o} />;
    case "checks":
      return <Checks beat={beat} o={o} />;
    case "held":
      return <Held beat={beat} o={o} />;
    case "confidence-strip":
      return <ConfStrip beat={beat} o={o} />;
    case "cannot-approve":
      return <CannotApprove beat={beat} o={o} />;
    case "ordered":
      return <Ordered beat={beat} o={o} />;
    case "verify":
      return <Verify o={o} />;
    case "threshold":
      return <Threshold o={o} />;
    case "evidence":
      return <Evidence o={o} />;
    case "traps":
      return <Traps o={o} />;
    case "fallback":
      return <Fallback o={o} />;
    case "other-agent":
      return <OtherAgent o={o} />;
    case "codex":
      return <Codex o={o} />;
    case "end":
      return <EndCard lines={o.lines} />;
  }
};
