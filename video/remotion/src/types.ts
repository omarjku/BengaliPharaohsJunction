import { Tone } from "./tokens";

export type Score = { label: string; value: number; out?: boolean };
export type EvidenceItem = { big: string; suffix?: string; label: string; tone?: Tone };
export type Trap = { lines: string[]; via?: string; stamp: string };

export type MediaSlot = {
  /** Path inside public/, e.g. "rec/take.webm". Missing file -> labelled placeholder card. */
  src: string;
  /** Name shown on the placeholder: "FOOTAGE: <label>". */
  label: string;
  /** Seek into the file, in seconds. */
  startFromSec?: number;
  frame: "phone" | "bleed";
};

export type Overlay =
  | { kind: "opening"; clock: string; question: string; tag: string }
  | { kind: "intake"; heading: string; big: string; sub: string; chips: string[] }
  | { kind: "reads"; header: string; lines: number; planted: string; stamp: string; note: string }
  | { kind: "checks"; chips: string[] }
  | { kind: "held"; item: string; qty: string; price: string; limitLabel: string; limit: string; stamp: string; amount: number; limitAmount: number }
  | { kind: "confidence-strip"; scores: Score[]; threshold: number; note: string }
  | { kind: "cannot-approve"; item: string; price: string; stamp: string; lines: string[] }
  | { kind: "ordered"; item: string; price: string; button: string; heldStamp: string; stamp: string; chips: string[] }
  | { kind: "verify"; stamp: string; steps: string[] }
  | { kind: "threshold"; lead: string; headline: string; scores: Score[]; threshold: number; zoneLeft: string; zoneRight: string }
  | { kind: "evidence"; items: EvidenceItem[]; note: string }
  | { kind: "traps"; items: Trap[] }
  | { kind: "fallback"; left: string; leftBadge: string; right: string; tags: [string, string] }
  | { kind: "other-agent"; nodes: [string, string, string]; verifyLabel: string; verifies: string[] }
  | { kind: "codex"; count: number; text: string }
  | { kind: "end"; lines: string[] };

export type Beat = {
  id: string;
  /** seconds */
  start: number;
  end: number;
  /** the spoken line, burned in as the caption */
  caption: string;
  overlay?: Overlay;
  mediaSlot?: MediaSlot;
};
