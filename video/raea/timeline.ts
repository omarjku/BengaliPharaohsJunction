export type CaptionSpeaker = "Omar" | "Zoha";

export type CaptionCue = {
  start: number;
  end: number;
  speaker: CaptionSpeaker;
  text: string;
};

export type DemoKeyframe = {
  at: number;
  x: number;
  y: number;
  scale: number;
  rotate: number;
};

export type DemoCallout = {
  start: number;
  end: number;
  text: string;
  detail: string;
  side: "left" | "right";
  labelX: number;
  labelY: number;
  anchorX: number;
  anchorY: number;
  accent: "lime" | "warm" | "teal";
};

export const FPS = 30;
export const DEMO_DURATION_SECONDS = 62;
export const CAPTION_BAND_TOP = 900;
export const CONTENT_SAFE_BOTTOM = 880;

const coldOpenDuration = 7;
const doorDuration = 3.5;
const explanationDuration = 8;
const trackDuration = 8.5;
const closerDuration = 9;
const demoStart = coldOpenDuration + doorDuration + explanationDuration;
const geminiStart = demoStart + DEMO_DURATION_SECONDS;
const codexStart = geminiStart + trackDuration;
const craciStart = codexStart + trackDuration;
const closerStart = craciStart + trackDuration;

export const TIMELINE = {
  totalSeconds: closerStart + closerDuration,
  sections: {
    coldOpen: { start: 0, duration: coldOpenDuration },
    door: { start: coldOpenDuration, duration: doorDuration },
    explanation: { start: coldOpenDuration + doorDuration, duration: explanationDuration },
    demo: { start: demoStart, duration: DEMO_DURATION_SECONDS },
    facts: { start: geminiStart, duration: trackDuration * 3 },
    gemini: { start: geminiStart, duration: trackDuration },
    codex: { start: codexStart, duration: trackDuration },
    craci: { start: craciStart, duration: trackDuration },
    closer: { start: closerStart, duration: closerDuration },
  },
  demo: {
    file: "demo.mp4",
    // Replace this single slot with the final portrait iPhone Mirroring take.
    duration: DEMO_DURATION_SECONDS,
    phone: { x: 760, y: 120, width: 400, height: 680 },
    keyframes: [
      { at: 0, x: 760, y: 120, scale: 0.94, rotate: -2.4 },
      { at: 9, x: 760, y: 120, scale: 1.02, rotate: -1.4 },
      { at: 19, x: 760, y: 120, scale: 1.08, rotate: -0.8 },
      { at: 29, x: 760, y: 120, scale: 1.0, rotate: -1.8 },
      { at: 39, x: 760, y: 120, scale: 1.08, rotate: -0.6 },
      { at: 49, x: 760, y: 120, scale: 1.04, rotate: -1.2 },
      { at: 61.9, x: 760, y: 120, scale: 1.1, rotate: -0.2 },
    ] satisfies DemoKeyframe[],
    callouts: [
      {
        start: 0.8,
        end: 8.2,
        text: "01 / READ",
        detail: "Gemini reads the handwritten Finnish list",
        side: "right",
        labelX: 1320,
        labelY: 228,
        anchorX: 0.78,
        anchorY: 0.26,
        accent: "teal",
      },
      {
        start: 8.7,
        end: 16.6,
        text: "02 / CHECK",
        detail: "Live Valio price, stock, delivery date",
        side: "right",
        labelX: 1320,
        labelY: 360,
        anchorX: 0.26,
        anchorY: 0.42,
        accent: "lime",
      },
      {
        start: 17.1,
        end: 25.0,
        text: "HELD",
        detail: "Decisions score: confident / asks the chef",
        side: "left",
        labelX: 76,
        labelY: 360,
        anchorX: 0.74,
        anchorY: 0.58,
        accent: "warm",
      },
      {
        start: 25.5,
        end: 33.5,
        text: "HELD",
        detail: "Held: over the EUR 1,500 limit",
        side: "left",
        labelX: 76,
        labelY: 520,
        anchorX: 0.7,
        anchorY: 0.7,
        accent: "warm",
      },
      {
        start: 34.0,
        end: 42.0,
        text: "03 / VOICE",
        detail: "Voice: change potatoes to 30 kg",
        side: "right",
        labelX: 1320,
        labelY: 520,
        anchorX: 0.3,
        anchorY: 0.36,
        accent: "teal",
      },
      {
        start: 42.5,
        end: 50.5,
        text: "APPROVE",
        detail: "Chef taps Approve",
        side: "left",
        labelX: 76,
        labelY: 676,
        anchorX: 0.72,
        anchorY: 0.78,
        accent: "lime",
      },
      {
        start: 51.0,
        end: 61.5,
        text: "ORDERED",
        detail: "Ordered · signed",
        side: "right",
        labelX: 1320,
        labelY: 676,
        anchorX: 0.28,
        anchorY: 0.82,
        accent: "lime",
      },
    ] satisfies DemoCallout[],
  },
  explanation: {
    cards: [
      { title: "A photo becomes a checked request.", body: "The agent reads the list, verifies facts, and keeps uncertainty visible.", steps: ["READ", "CHECK", "HOLD"] },
      { title: "The door checks more than text.", body: "Price, stock, date, pack size, spend, and the kitchen's rules stay in the loop.", steps: ["FACTS", "RULES", "EVIDENCE"] },
      { title: "The chef keeps the final say.", body: "The agent can prepare an order. Only the approver can sign it.", steps: ["PREPARE", "ASK", "APPROVE"] },
    ],
  },
  facts: [
    {
      id: "gemini",
      label: "GEMINI",
      number: "0.70",
      headline: "Decisions API · gemini-decision-1",
      line: "A calibrated score tells the agent when to act and when to ask.",
      facts: [
        "Every assumption gets a yes-probability, up to 40 per call; Gemini reads the handwritten Finnish list and Gemini Live uses the same tools.",
        "coffee milk 0.115 → ask · lactose-free milk 0.897 → act.",
        "Gemini 4 Hydrogen + function calling drives tools; it cannot touch money. 0 unsafe auto-orders in 164 chat tests, including 10 injection attempts.",
      ],
      visual: {
        threshold: 0.7,
        points: [
          { label: "coffee milk", value: 0.115, verdict: "ask" },
          { label: "lactose-free milk", value: 0.897, verdict: "act" },
        ],
        footer: "handwritten Finnish list · Gemini Live · tap gate",
      },
    },
    {
      id: "codex",
      label: "CODEX",
      number: "42",
      headline: "main commits say “Built by Codex”",
      line: "The code was built, attacked, and tested against the real Gemini loop.",
      facts: [
        "Up to 5 Codex workers in parallel, each in its own git worktree.",
        "Review caught: a free-from milk cleared a peanut ban. Fixed the same night.",
        "787 automated tests pass. Every run is logged in docs/CODEX.md.",
      ],
      gitLog: [
        "git log origin/main --grep='Built by Codex' -i",
        "98eca26 Built by Codex · tool results",
        "afefeb9 Built by Codex · product + price",
        "0ee4199 Built by Codex · voice holds",
        "4ae7920 Built by Codex · allergens unknown",
        "1664f12 Built by Codex · CRACI provenance",
      ],
    },
    {
      id: "craci",
      label: "CRACI",
      number: "351",
      headline: "CycloneDX SBOM + network trace",
      line: "Every signed order names the build that signed it.",
      facts: [
        "All 7 CI jobs run on CRACI runners.",
        "170 pip + 181 npm components · 17 network destinations · status ok.",
        "CRACI flagged vulnerabilities at midnight; FastAPI, Starlette, cryptography, and minimatch were upgraded that night.",
      ],
      build: {
        status: "ok",
        componentCounts: { pip: 170, npm: 181 },
        networkDestinations: 17,
        sbomSha256: "49730579fece",
      },
    },
  ],
  closer: {
    repo: "github.com/omarjku/BengaliPharaohsJunction",
    site: "valio-front-door.onrender.com",
    disclaimer: "Valio challenge mock · no real orders or payments",
    team: "Omar Kassem & Fathia Fairuz Zoha",
  },
  voiceover: {
    enabled: false,
    file: "voiceover.wav",
  },
} as const;

export const frames = (seconds: number) => Math.round(seconds * FPS);
