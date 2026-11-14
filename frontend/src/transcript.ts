// Talk (Gemini Live): turns the live transcript events into clean thread lines.
// Pure: no React, no side effects, never mutates what it is given.
//
// The server sends each speaker's words in fragments ({final:false}) and the whole sentence once at the end of the turn
// ({final:true}). A fragment can end in the middle of a Gemini tag (for example "<no" then " speech>{pause}"), so the raw
// text of an open line is kept and cleaned as a whole, never fragment by fragment.

export type TranscriptRole = 'user' | 'agent'
export type TranscriptEvent = { role: TranscriptRole; text: string; final: boolean; turn_id?: number; cumulative?: boolean }

/** A spoken line in the thread. `partial` marks the line still being formed; `raw` is its uncleaned text so far. */
export type TranscriptLine = { id: number; kind: TranscriptRole; text: string; partial?: boolean; raw?: string; turn_id?: number }

const CLOSED_ANGLE = /<[A-Za-z][A-Za-z _-]{0,40}>/g // <no speech>, <noise>; not "5 < 10" or "a > b"
const CLOSED_CURLY = /\{[^{}\n]{0,40}\}/g // {pause}, {laughs}
const OPEN_ANGLE_TAIL = /<[A-Za-z][A-Za-z _-]{0,40}$/ // a tag still arriving: "as <no"
const OPEN_CURLY_TAIL = /\{[^{}\n]{0,40}$/

/** Removes complete <tag> and {tag} markers and tidies spaces. A lone "<" or ">" in real speech is left alone. */
export function cleanText(s: string): string {
  return s.replace(CLOSED_ANGLE, '').replace(CLOSED_CURLY, '').replace(/\s+/g, ' ').trim()
}

/** What to show while a line is still open: complete tags removed, and a tag that has only started hidden too. */
function showing(raw: string): string {
  return cleanText(raw).replace(OPEN_ANGLE_TAIL, '').replace(OPEN_CURLY_TAIL, '').trim()
}

const isLine = (it: { kind: string }): it is { kind: string } & TranscriptLine => it.kind === 'user' || it.kind === 'agent'

/**
 * Applies one transcript event to the thread and returns a NEW array.
 * Per speaker there is at most one open line (the last one, found by searching backwards):
 * a fragment is appended to it (or opens it); a final replaces its text with the whole sentence and closes it.
 * A final with no open line makes a closed one. Lines whose cleaned text is empty are never shown.
 * If the server ever sends cumulative text, a fragment that starts with what we already have replaces it.
 */
export function mergeTranscript<T extends { kind: string }>(thread: T[], ev: TranscriptEvent, nextId: () => number): T[] {
  let at = -1
  for (let i = thread.length - 1; i >= 0; i--) {
    const it = thread[i]
    if (isLine(it) && it.kind === ev.role && it.partial === true &&
        (ev.turn_id === undefined || it.turn_id === ev.turn_id)) {
      at = i
      break
    }
  }
  const open = at >= 0 ? (thread[at] as unknown as TranscriptLine) : null

  if (ev.final) {
    const text = cleanText(ev.text)
    if (open) {
      if (!text) return thread.filter((_, i) => i !== at)
      const closed: TranscriptLine = { id: open.id, kind: open.kind, text, partial: false, turn_id: ev.turn_id ?? open.turn_id }
      return thread.map((it, i) => (i === at ? (closed as unknown as T) : it))
    }
    if (!text) return thread
    return [...thread, { id: nextId(), kind: ev.role, text, partial: false } as unknown as T]
  }

  const base = open?.raw ?? ''
  const raw = ev.cumulative ? ev.text : base && ev.text.startsWith(base) ? ev.text : base + ev.text
  const text = showing(raw)
  if (!text) return open ? thread.filter((_, i) => i !== at) : thread
  if (open) {
    const next: TranscriptLine = { id: open.id, kind: open.kind, text, partial: true, raw, turn_id: ev.turn_id ?? open.turn_id }
    return thread.map((it, i) => (i === at ? (next as unknown as T) : it))
  }
  if (!raw.trim()) return thread
  return [...thread, { id: nextId(), kind: ev.role, text, partial: true, raw, turn_id: ev.turn_id } as unknown as T]
}
