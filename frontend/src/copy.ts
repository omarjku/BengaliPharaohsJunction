// Everything the chef reads that isn't data lives here, so wording can be tuned in one place.
// Voice: a calm colleague. Short sentences, plain words, the number that matters, no system-speak.
import type { Reason } from './types'

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
const UNITS: Record<string, string> = { ST: 'unit', KPL: 'piece', KI: 'case', PAK: 'pack', KG: 'kg', L: 'litre', LTR: 'litre', PS: 'bag', RS: 'tray' }
export const unitName = (code: string | null | undefined) => (code ? (UNITS[code.toUpperCase()] ?? code) : 'unit')
