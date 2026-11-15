export type CaptionSpeaker = "Omar" | "Zoha";

export type CaptionCue = {
  start: number;
  end: number;
  speaker: CaptionSpeaker;
  text: string;
};

export const FPS = 30;

export const TIMELINE = {
  totalSeconds: 117,
  sections: {
    coldOpen: { start: 0, duration: 8 },
    door: { start: 8, duration: 3 },
    explanation: { start: 11, duration: 14 },
    demo: { start: 25, duration: 66 },
    facts: { start: 91, duration: 18 },
    closer: { start: 109, duration: 8 },
  },
  explanation: {
    cards: [
      {
        title: "At 06:00, the kitchen cannot guess.",
        body: "A photo or voice request has to become a checked decision before the cut-off closes.",
        steps: ["Photo or voice", "Chef's list", "One clear request"],
      },
      {
        title: "Front Door checks the door.",
        body: "It checks Valio price, stock, delivery, and pack sizes before anything becomes an order.",
        steps: ["Valio price + stock", "Delivery check", "Held card"],
      },
      {
        title: "The chef keeps the final say.",
        body: "If the decision needs approval, the cart waits. Approve it, and the order is signed and recorded.",
        steps: ["Chef approves", "Signed order", "Kitchen history"],
      },
    ],
  },
  demo: {
    file: "demo.mp4",
    applySpeedChanges: false,
    crop: { x: 0.05, y: 0.02, width: 0.9, height: 0.96 },
    callouts: [
      { start: 0.6, end: 8.5, text: "Gemini reads the Finnish list" },
      { start: 10.0, end: 18.5, text: "Live Valio price + stock" },
      { start: 20.0, end: 29.0, text: "Held: above EUR 1,500 limit" },
      { start: 33.0, end: 41.0, text: "Voice change" },
      { start: 45.0, end: 53.0, text: "Chef approves" },
      { start: 55.0, end: 65.4, text: "Signed order" },
    ],
    speedRanges: [
      { start: 8.8, end: 16.0, rate: 4 },
      { start: 30.0, end: 38.0, rate: 4 },
      { start: 42.0, end: 47.0, rate: 4 },
    ],
  },
  facts: [
    {
      label: "GEMINI",
      headline: "0.70 Decisions threshold",
      body: "A confidence score decides when the agent asks the chef. It cannot approve an order.",
    },
    {
      label: "CODEX",
      headline: "29 “Built by Codex” commits on main",
      body: "The documented split: Codex built and attacked the core, the Gemini agent, and the safety paths.",
    },
    {
      label: "CRACI",
      headline: "CI on the craci runner",
      body: "The build evidence ties the order to an SBOM and network trace at /.well-known/front-door-build.json.",
    },
  ],
  closer: {
    coldOpenStart: 4,
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

