// The audit trail as the chef thinks of it: one row per request, titled with how it ended, steps inside.
import type { Tone } from './format'
import type { Copy } from './i18n'
import type { AuditEntry } from './types'

export type Step = { e: AuditEntry; what: string; tone: Tone }
export type OutcomeKey = keyof Copy['UI']['history']['outcome']
export type Group = { key: string; at: string; title: string; outcome: string; outcomeKey: OutcomeKey; tone: Tone; steps: Step[]; orderId: string | null }

const HUMAN = /^human:(.+?)(?::(approve|reject|mandate))?$/

// One step in plain words: who did what.
export function step(e: AuditEntry, c: Copy): Step {
  const t = c.UI.history.step
  const human = HUMAN.exec(e.actor)
  const o = e.decision.outcome
  const tone: Tone = o === 'AUTO' ? 'good' : o === 'DECLINE' ? 'bad' : 'warn'
  if (human?.[2] === 'approve') return { e, tone: 'good', what: t.approved(human[1]) }
  if (human?.[2] === 'reject') return { e, tone: 'neutral', what: t.rejected(human[1]) }
  if (human?.[2] === 'mandate') return { e, tone: 'neutral', what: t.rulesChanged(human[1]) }
  if (e.actor === 'buyer_agent')
    return { e, tone, what: o === 'AUTO' ? t.agentSent : o === 'DECLINE' ? t.agentDeclined : t.agentAsked }
  if (e.actor === 'valio_front_door')
    return { e, tone, what: o === 'AUTO' ? t.valioConfirmed : o === 'DECLINE' ? t.valioRefused : t.valioHeld }
  return { e, tone, what: human?.[1] ?? e.actor }
}

// How the request ended, from its last step.
function outcome(steps: Step[]): [Tone, OutcomeKey] {
  const last = steps[steps.length - 1]
  const human = HUMAN.exec(last.e.actor)?.[2]
  if (human === 'approve') return ['good', 'ordered']
  if (human === 'reject') return ['neutral', 'rejected']
  if (human === 'mandate') return ['neutral', 'rules']
  const o = last.e.decision.outcome
  if (last.e.actor === 'valio_front_door') return o === 'AUTO' ? ['good', 'ordered'] : o === 'DECLINE' ? ['bad', 'notOrdered'] : ['warn', 'held']
  return o === 'AUTO' ? ['neutral', 'sent'] : o === 'DECLINE' ? ['bad', 'notOrdered'] : ['warn', 'needed']
}

const said = (e: AuditEntry, c: Copy) => c.humanize(e.input.request.text.replace(/^Order via Valio front door:\s*/, '').replace(/^Menu for \d+ covers:\s*(?=menu\b)/i, ''))
const NEAR_MS = 5 * 60_000 // the front door answers the agent within seconds; 5 minutes is generous

// Entries arrive oldest first; groups come back newest first.
export function groupHistory(entries: AuditEntry[], c: Copy): Group[] {
  const groups: (Omit<Group, 'outcome' | 'outcomeKey' | 'tone' | 'title'> & { title: string | null })[] = []
  for (const e of entries) {
    const s = step(e, c)
    const human = HUMAN.exec(e.actor)?.[2]
    const t = new Date(e.timestamp).getTime()
    const last = groups[groups.length - 1]
    // Since QA round 2 the agent's line comes after the front door's and names it (FRONT_DOOR, door_audit_id):
    // it joins that request, first among its steps, and its words become the title.
    const door = e.actor === 'buyer_agent' ? e.decision.reasons.find((r) => r.code === 'FRONT_DOOR')?.facts.door_audit_id : null
    const doorGroup = door ? groups.find((x) => x.steps.some((st) => st.e.id === door)) : null
    if (doorGroup) {
      doorGroup.steps.unshift(s)
      doorGroup.title = said(e, c)
      continue
    }
    let g = null as (typeof groups)[number] | null
    if (human === 'approve' || human === 'reject') g = groups.find((x) => x.orderId === e.input.request.id) ?? null
    else if (e.actor === 'valio_front_door' && last && !last.orderId && last.steps[0].e.actor === 'buyer_agent'
      && t - new Date(last.steps[last.steps.length - 1].e.timestamp).getTime() < NEAR_MS) g = last
    if (!g) {
      g = { key: e.id, at: e.timestamp, title: null, steps: [], orderId: null }
      groups.push(g)
    }
    g.steps.push(s)
    if (e.actor === 'valio_front_door') g.orderId = e.input.request.id
    if (!g.title && !human) g.title = said(e, c) // the chef's own words when the agent saw them first
    if (human === 'mandate') g.title = c.UI.history.yourRules
  }
  return groups
    .map((g) => {
      const [tone, key] = outcome(g.steps)
      return { ...g, title: g.title ?? said(g.steps[0].e, c), tone, outcomeKey: key, outcome: c.UI.history.outcome[key] }
    })
    .reverse()
}

const HELSINKI = 'Europe/Helsinki'
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: HELSINKI })
const dayKey = new Intl.DateTimeFormat('en-CA', { timeZone: HELSINKI }) // YYYY-MM-DD in Helsinki
export const time = (iso: string) => clock.format(new Date(iso))

function dayLabel(iso: string, c: Copy, now = new Date()): string {
  const d = dayKey.format(new Date(iso))
  if (d === dayKey.format(now)) return c.UI.history.today
  if (d === dayKey.format(new Date(now.getTime() - 86_400_000))) return c.UI.history.yesterday
  return c.longDay(iso)
}

// Groups (newest first) under day headings: Today, Yesterday, then dates.
export function byDay(groups: Group[], c: Copy): [string, Group[]][] {
  const days: [string, Group[]][] = []
  for (const g of groups) {
    const label = dayLabel(g.at, c)
    const last = days[days.length - 1]
    if (last?.[0] === label) last[1].push(g)
    else days.push([label, [g]])
  }
  return days
}
