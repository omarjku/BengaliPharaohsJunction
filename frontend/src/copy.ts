// Everything the chef reads that isn't data lives here, so wording can be tuned in one place.
// Voice: a calm colleague. Short sentences, plain words, the number that matters, no system-speak.
import type { Mandate, RuleChange, Reason } from './types'

const euro = (cents: number) => {
  const whole = cents % 100 === 0
  return new Intl.NumberFormat('en-IE', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2,
  }).format(cents / 100)
}
const num = (v: unknown) => (typeof v === 'number' ? v : null)

// The headline for a reason, built from its facts when we know the code; otherwise the backend's own sentence.
export function headline(r: Reason): string {
  const f = r.facts
  switch (r.code) {
    case 'SPEND_OVER_LIMIT': {
      const total = num(f.total_cents), limit = num(f.limit_cents)
      if (total !== null && limit !== null) return `${euro(total - limit)} over your ${euro(limit)} limit.`
      break
    }
    case 'LINE_OVER_CAP': {
      const total = num(f.line_total_cents), cap = num(f.cap_cents)
      if (total !== null && cap !== null) return `${euro(total - cap)} over your ${euro(cap)} limit for one product.`
      break
    }
    case 'WEEKLY_BUDGET_EXCEEDED': {
      const spent = num(f.spent_7d_cents), total = num(f.total_cents), budget = num(f.budget_cents)
      if (spent !== null && total !== null && budget !== null)
        return `This takes the week ${euro(spent + total - budget)} over your ${euro(budget)} budget.`
      break
    }
    case 'STOCK_PARTIAL': {
      const have = num(f.available), want = num(f.requested)
      if (have !== null && want !== null)
        return `Valio only has ${have.toLocaleString('en-US')} of the ${want.toLocaleString('en-US')} you need.`
      break
    }
    case 'STOCK_NONE':
      return 'Valio is out of this right now.'
    case 'CUTOFF_PASSED':
      return 'Too late to order this for that day.'
    case 'DATE_NOT_HONOURED':
      return 'Valio can’t deliver this on the day you picked.'
    case 'LOW_RELIABILITY': {
      const rel = num(f.reliability)
      if (rel !== null) return `This one arrives on time only ${Math.round(rel * 100)}% of the time.`
      break
    }
    case 'MANDATE_MISSING':
      return 'There are no ordering rules for this kitchen yet.'
    case 'QTY_AMBIGUOUS':
    case 'QTY_UNKNOWN':
      return 'How much do you need? The amount wasn’t clear.'
    case 'LOW_CONFIDENCE':
      // Gemini's own reason sits under "Why this …"; the headline just says what it means for the chef.
      if (r.severity === 'ASK_HUMAN' && num(f.confidence) !== null) return 'Not sure this is the product you meant.'
      break
    case 'PRICE_CHANGED':
      return 'The price changed since you last saw it.'
  }
  return r.message
}

// One word or two for where an order stands. Status colour always comes with these words.
export const STATUS: Record<string, string> = {
  confirmed: 'Ordered',
  pending_approval: 'Needs your OK',
  refused: 'Not ordered',
  rejected: 'Rejected',
  AUTO: 'Ordered',
  ASK_HUMAN: 'Needs your OK',
  DECLINE: 'Not ordered',
}

// Gemini Decisions API confidence as a sentence; the number stays, but second.
export const CONFIDENT_AT = 0.8
export const confidenceSentence = (c: number) =>
  c >= CONFIDENT_AT ? 'Sure this is what you meant' : 'Not sure this is what you asked for'

export const RUNNING = 'Reading your request, then checking the catalogue, Valio stock and prices…'
export const EXAMPLE = '1000 L lactose-free milk for Monday'

// Valio's sales-unit codes in words. Unknown codes are shown as they are.
const UNITS: Record<string, string> = {
  ST: 'unit', KPL: 'piece', KI: 'case', CS: 'case', PAK: 'pack', PKT: 'pack', KG: 'kg', L: 'litre', LTR: 'litre',
  PS: 'bag', BAG: 'bag', RAS: 'box', RS: 'tray', PLO: 'bottle', TLK: 'tin',
}
export const unitName = (code: string | null | undefined) => (code ? (UNITS[code.toUpperCase()] ?? code) : 'unit')

// --- Rules, in the chef's language.
const ALLERGENS: Record<string, string> = {
  AM: 'milk', AE: 'egg', AF: 'fish', AN: 'tree nuts', AP: 'peanuts', AY: 'soy', AW: 'gluten', AC: 'crustaceans',
  AS: 'sesame', BC: 'celery', BM: 'mustard', AU: 'sulphites', NL: 'lupin', UM: 'molluscs', UW: 'wheat',
}
export const allergen = (v: unknown) => ALLERGENS[String(v).toUpperCase()] ?? String(v).toLowerCase()
const cents = (v: unknown) => euro(Math.round(Number(v)))
const words = (v: unknown) => String(v).toLowerCase().replace(/_/g, ' ')

// The rules in force, one plain sentence each, with the chef's own words when the rule came from them.
export function ruleLines(m: Mandate): { text: string; said: string | null }[] {
  const out: { text: string; said: string | null }[] = []
  for (const r of m.hard_rules) {
    const said = r.source_text?.startsWith('Default:') ? null : r.source_text
    switch (r.kind) {
      case 'excluded_allergen': out.push({ text: `Never anything with ${allergen(r.value)}.`, said }); break
      case 'required_claim': out.push({ text: `Only products that are ${words(r.value)}.`, said }); break
      case 'auto_approve_limit_cents':
        out.push({ text: `Orders up to ${cents(r.value)} go through on their own. Above that, you’re asked.`, said }); break
      case 'max_unit_price_cents': out.push({ text: `Never more than ${cents(r.value)} per unit.`, said }); break
      case 'min_delivery_reliability':
        out.push({ text: `You’re asked before anything that’s on time less than ${Math.round(Number(r.value) * 100)}% of the time.`, said }); break
      default: out.push({ text: said ?? `${words(r.kind)}: ${r.value}`, said: null })
    }
  }
  out.push({ text: `At most ${euro(m.per_line_cap_cents)} for one product in an order.`, said: null })
  if (m.weekly_budget_cents) out.push({ text: `A budget of ${euro(m.weekly_budget_cents)} a week.`, said: null })
  if (m.blocklist.length) out.push({ text: `${m.blocklist.length} product${m.blocklist.length > 1 ? 's are' : ' is'} never ordered.`, said: null })
  out.push({
    text: { ask: 'When the agent can’t check something, it asks you.', decline: 'When the agent can’t check something, it doesn’t order.', approve: 'When the agent can’t check something, it orders anyway.' }[m.uncertainty_policy] ?? '',
    said: null,
  })
  for (const g of m.guidance) out.push({ text: `Preference: ${g.text}`, said: null })
  if (m.expires_at) out.push({ text: `These rules end on ${new Date(m.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })}.`, said: null })
  return out
}

// The chef's own words for the current rules: the starting text when they change them, so nothing drops by accident.
// Limits without the chef's own words (per-line cap, weekly budget) are written out too, or recompiling would drop them.
export const ruleWords = (m: Mandate) =>
  [
    ...new Set([
      ...m.hard_rules.map((r) => r.source_text).filter((t): t is string => !!t && !t.startsWith('Default:')),
      `At most ${euro(m.per_line_cap_cents)} for one product in an order.`,
      ...(m.weekly_budget_cents ? [`A budget of ${euro(m.weekly_budget_cents)} a week.`] : []),
      ...m.guidance.map((g) => g.text),
    ]),
  ].join('\n')

const CHANGE_WORD: Record<string, string> = { tighter: 'Stricter', looser: 'Looser', changed: 'Changed' }
export const changeWord = (c: RuleChange) => CHANGE_WORD[c.change] ?? c.change
// The backend's change text, with euros written the way a chef writes them.
export const changeText = (c: RuleChange) => {
  if (c.field === 'guidance') return `Preferences: ${Array.isArray(c.after) && c.after.length ? c.after.join(' ') : 'none'}`
  const t = c.text.replace(/EUR ([\d,]+)\.00/g, '€$1').replace(/EUR ([\d,.]+)/g, '€$1').replace(/ → /g, ' to ')
  return t.charAt(0).toUpperCase() + t.slice(1)
}
// The second confirm for loosening, said plainly.
export function loosenSentence(c: RuleChange): string {
  if (c.field === 'excluded_allergens' && c.after == null) return `You’re removing the ${allergen(c.before)} exclusion.`
  if (c.field === 'required_claims' && c.after == null) return `You’re dropping the rule that products must be ${words(c.before)}.`
  if (c.field === 'blocklist' && c.after == null) return `You’re unblocking product ${String(c.before)}.`
  if (c.field === 'min_delivery_reliability' && c.after == null) return 'You’re removing the on-time delivery rule.'
  if (c.field === 'uncertainty_policy') return 'When the agent can’t check something, it will order anyway.'
  const limit = /^(.*?): (.*) to (.*?)( \(no limit at all\))?$/.exec(changeText(c))
  if (c.field.endsWith('_cents') && limit)
    return limit[3] === 'none' ? `You’re removing the ${limit[1].toLowerCase()}.` : `You’re raising the ${limit[1].toLowerCase()} from ${limit[2]} to ${limit[3]}.`
  return `${changeText(c)}.`
}
