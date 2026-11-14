// Everything the chef reads that isn't data lives here, so wording can be tuned in one place.
// Voice: a calm colleague. Short sentences, plain words, the number that matters, no system-speak.
import { flagLabel, formatCents, formatDateTime, formatDay, formatEuro, ownWords, stockText } from './format'
import type { Mandate, RuleChange, Reason } from './types'

const euro = (cents: number) => {
  const whole = cents % 100 === 0
  return new Intl.NumberFormat('en-IE', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2,
  }).format(cents / 100)
}
const num = (v: unknown) => (typeof v === 'number' ? v : null)

// The headline for a reason, built from its facts when we know the code; otherwise the backend's own sentence.
const DOOR_STATUS: Record<string, string> = { confirmed: 'confirmed', pending_approval: 'held for your OK', refused: 'refused', rejected: 'rejected' }

// The backend's questions back to the chef, said in this language. Unknown ones are shown as the backend wrote them.
export function question(q: string, r?: Reason | null): string {
  const mins = num(r?.facts.minutes_ago)
  if (mins !== null) return `You ordered this ${mins} minute${mins === 1 ? '' : 's'} ago. Order again?`
  if (/^Which one did you mean: /.test(q)) return 'Which one did you mean?' // the options are buttons under it
  const past = /^\w+ (\d{1,2} \w+ \d{4}) is in the past\./.exec(q)
  if (past) return `${past[1].replace(/^0/, '')} is in the past. Which delivery day?`
  return q
}

export function headline(r: Reason): string {
  const f = r.facts
  switch (r.code) {
    case 'SPEND_OVER_LIMIT': {
      const total = num(f.total_cents), limit = num(f.limit_cents)
      if (total !== null && limit !== null) return `${euro(total - limit)} over the ${euro(limit)} order limit.`
      break
    }
    case 'LINE_OVER_CAP': {
      const total = num(f.line_total_cents), cap = num(f.cap_cents)
      if (total !== null && cap !== null) return `${euro(total - cap)} over the ${euro(cap)} limit for one product.`
      break
    }
    case 'WEEKLY_BUDGET_EXCEEDED': {
      const spent = num(f.spent_7d_cents), total = num(f.total_cents), budget = num(f.budget_cents)
      if (spent !== null && total !== null && budget !== null)
        return `This takes the week ${euro(spent + total - budget)} over the ${euro(budget)} weekly budget.`
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
      if (r.severity === 'ASK_HUMAN' && num(f.confidence) !== null) return 'Best guess, please check.'
      break
    case 'PRICE_CHANGED':
      return 'The price changed since you last saw it.'
    case 'CONFIDENCE_OK':
      if (num(f.confidence) !== null) return `${matched(num(f.confidence)!)}.`
      break
    case 'FRONT_DOOR':
      if (typeof f.status === 'string') return `Sent to Valio’s front door: ${DOOR_STATUS[f.status] ?? f.status}.`
      break
  }
  return r.message
}

// Gemini Decisions API confidence, in one voice everywhere. Floored like the backend, so 79.9% never reads as 80%.
export const CONFIDENT_AT = 0.8
export const pct = (c: number) => `${Math.floor(c * 100)}%`
export const matched = (c: number) => (c >= CONFIDENT_AT ? `Matched by Gemini · ${pct(c)}` : `Gemini’s best guess · ${pct(c)}, please check`)
export const CONFIDENCE_MEANS: string = 'The percentage is Gemini’s confidence that this is the product you meant. Below 80%, the agent asks you first.'

// Backend sentences shown as they are, minus the machine bits.
export const humanize = (msg: string) =>
  msg
    .replace(/\s*\((\d\.\d+|\d+%) vs your (\d\.\d+) threshold\)/g, (_, _c, t) => ` (below the ${Math.round(Number(t) * 100)}% it needs to order on its own)`)
    .replace(/EUR ([\d,]+)\.00/g, '€$1')
    .replace(/\(net of VAT\)/g, 'excl. VAT')
    .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, 'the order')

// Catalogue names, tidied for reading: no ®/™, "1 l" → "1 L", no "Suomesta" (from Finland), no SHOUTING.
export function tidyName(name: string): string {
  let n = name.replace(/[®™]/g, '').replace(/\bSuomesta\b/gi, '').replace(/(\d)\s?l\b/g, '$1 L').replace(/\s{2,}/g, ' ').trim()
  if (n === n.toUpperCase() && /[A-Z]{3}/.test(n)) n = n.charAt(0) + n.slice(1).toLowerCase()
  return n
}

export const RUNNING: string = 'Reading your request, then checking the catalogue, Valio stock and prices…'
export const EXAMPLE: string = '1000 L lactose-free milk for Monday'
// One box for everyone: a milk order, a kebab shop's meat, a whole menu. Shown as cycling grey examples and as Try links.
export const EXAMPLES = [
  '1000 L lactose-free milk for Monday',
  '20 kg döner kebab meat for the rotisserie, Friday',
  'Menu for 80 guests: reindeer stew, mashed potatoes, lingonberry cheesecake',
]
export const TRY = EXAMPLES
export const HISTORY_INTRO: string = 'What was ordered, held or refused.'

// Valio's sales-unit codes in words. Unknown codes are shown as they are.
const UNITS: Record<string, string> = {
  ST: 'pack', KPL: 'piece', KI: 'case', CS: 'case', PAK: 'pack', PKT: 'pack', KG: 'kg', L: 'litre', LTR: 'litre',
  PS: 'bag', BAG: 'bag', RAS: 'box', RS: 'tray', PLO: 'bottle', TLK: 'tin', KRT: 'carton', PRK: 'jar',
}
export const unitName = (code: string | null | undefined) => (code ? (UNITS[code.toUpperCase()] ?? code) : 'unit')
const PLURAL: Record<string, string> = { box: 'boxes', kg: 'kg', g: 'g', L: 'L' }
// "640 packs", "1 case", "27.2 kg".
export const amountOf = (n: number, code: string | null | undefined) => {
  const u = unitName(code)
  return `${n.toLocaleString('en-US')} ${n === 1 ? u : (PLURAL[u] ?? `${u}s`)}`
}

// --- Rules, in the chef's language.
const ALLERGENS: Record<string, string> = {
  AM: 'milk', AE: 'egg', AF: 'fish', AN: 'tree nuts', AP: 'peanuts', AY: 'soy', AW: 'gluten', AC: 'crustaceans',
  AS: 'sesame', BC: 'celery', BM: 'mustard', AU: 'sulphites', NL: 'lupin', UM: 'molluscs', UW: 'wheat',
}
export const allergen = (v: unknown) => ALLERGENS[String(v).toUpperCase()] ?? String(v).toLowerCase()
const cents = (v: unknown) => euro(Math.round(Number(v)))
const words = (v: unknown) => String(v).toLowerCase().replace(/_/g, ' ')

// The rules in force, one plain sentence each, with the chef's own words when the rule came from them.
// `words`, when set, is how the line is written back into the editable text (exact ids and dates).
export function ruleLines(m: Mandate): { text: string; said: string | null; words?: string }[] {
  const out: { text: string; said: string | null; words?: string }[] = []
  for (const r of m.hard_rules) {
    const said = ownWords(m, r.source_text)
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
  if (m.blocklist.length)
    out.push({ text: `${m.blocklist.length} product${m.blocklist.length > 1 ? 's are' : ' is'} never ordered.`, said: null, words: `Never order product ${m.blocklist.join(', ')}.` })
  out.push({
    text: { ask: 'When the agent can’t check something, it asks you.', decline: 'When the agent can’t check something, it doesn’t order.', approve: 'When the agent can’t check something, it orders anyway.' }[m.uncertainty_policy] ?? '',
    said: null,
  })
  for (const g of m.guidance) out.push({ text: `Preference: ${g.text}`, said: null })
  if (m.expires_at)
    out.push({ text: `These rules end on ${new Date(m.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })}.`, said: null, words: `These rules end on ${m.expires_at.slice(0, 10)}.` })
  return out
}

// The starting text when the chef changes their rules: every rule as one plain sentence (blocked products and the end
// date included), so recompiling it keeps everything and only what the chef edits changes. Not the source quotes: the
// compiler may give every rule the whole original text.
export const ruleWords = (m: Mandate) => [...new Set(ruleLines(m).map((l) => l.words ?? l.text).filter(Boolean))].join('\n')

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

// --- Formatting, in this language's style (Finnish: 1 560,00 €, ma 16.11.).
export const LANG = 'en' as const
export const money = (cents: number) => formatCents(cents)
export const price = (euros: number) => formatEuro(euros)
export const day = (ymd: string) => formatDay(ymd)
export const dateTime = (iso: string) => formatDateTime(iso)
export const longDay = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Helsinki' }).format(new Date(iso))
export const weekday = (ymd: string) => new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' }).format(new Date(`${ymd}T00:00:00Z`))
export const count = (n: number) => n.toLocaleString('en-US')
export const stock = (n: number) => stockText(n)
export const flag = (f: string) => flagLabel(f)
export const country = (code: string) => {
  try {
    return new Intl.DisplayNames(['en'], { type: 'region' }).of(code.toUpperCase()) ?? code.toUpperCase()
  } catch {
    return code.toUpperCase()
  }
}
const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

// --- Every other word on screen.
export const UI = {
  nav: { main: 'Main', order: 'Order', history: 'History', rules: 'Rules', keys: 'Keys' },
  lang: { switchTo: 'Suomeksi', short: 'FI', label: 'FI, suomeksi' }, // the switch offers the other language, in that language
  greeting: (part: 'morning' | 'afternoon' | 'evening', name: string | null, waiting: number) =>
    `${{ morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening' }[part]}${name ? `, ${name}` : ''}. ` +
    (waiting === 0 ? 'Nothing waiting for you.' : `${waiting} ${plural(waiting, 'order is', 'orders are')} waiting for your OK in History.`),
  offline: {
    title: 'Can’t reach the ordering service.',
    body: 'Your request will fail until it’s back. If you run it yourself, start the backend on port 8000.',
  },
  // Shown on every screen in mock mode, so nobody mistakes a canned answer for a real one.
  mock: {
    title: 'Demo data, not the real service.',
    body: 'Answers come from a few canned examples and nothing is really ordered. For real answers, run the backend and open the app without ?mock=1.',
  },
  failed: 'That didn’t go through.',
  ask: {
    label: 'What do you need?',
    help: (examples: string[]) => `An order, or a whole menu with the number of guests. For example: ${examples.join('; ')}.`,
    delivery: 'Delivery',
    orDay: 'or the day you write',
    dateAria: 'Delivery date (optional: otherwise the day in your words, or next Monday)',
    ask: 'Ask the agent',
    again: 'Ask again',
    asking: 'Asking…',
    announce: 'Asking the agent…',
    tryDemo: 'Demo data. Try: ',
    try: 'Try: ',
    edit: 'Edit',
  },
  question: {
    status: 'One thing first',
    more: 'Tell me a bit more',
    plan: 'Plan the cart',
    planning: 'Planning…',
    guests: (n: number) => `For ${n} guests.`,
    answer: 'Your answer',
    send: 'Send',
    sending: 'Sending…',
    orderAgain: 'Order again',
    leave: 'No, leave it',
    leftAlone: 'Nothing was ordered.',
    listening: 'Listening for your answer… tap the mic to send.',
    cancel: 'Cancel',
    expired: 'That question expired. Please ask again.',
    reask: 'Ask again',
    edit: 'Edit your request',
    days: 'Delivery days',
    options: 'Options',
  },
  keys: {
    title: 'Keys',
    firstTitle: 'Before your first order',
    firstIntro: 'Paste the two keys from your Valio Aimo account. You only do this once.',
    start: 'Save and start',
    save: 'Save keys',
    cancel: 'Cancel',
    agent: 'Agent key',
    agentHelp: 'Lets the agent place orders for your kitchen.',
    approver: 'Approver key',
    approverHelp: 'Yours alone. It approves orders and shows the history.',
    tip: 'Tip: a setup link fills these in.',
    fromLink: 'Keys saved on this device.',
    switchQ: (kitchen: string | null) => (kitchen ? `Switch this device to ${kitchen}?` : 'Switch this device to the keys in this link?'),
    switchTo: 'Switch',
    keepCurrent: 'Keep current',
    linkChecking: 'Checking the setup link…',
    linkInvalid: 'This setup link isn’t valid.',
    linkKept: 'Your current keys are kept.',
    ok: 'OK',
    show: 'Show',
    hide: 'Hide',
  },
  status: { ordered: 'Ordered', yourCall: 'Your call', rejected: 'Rejected', notOrdered: 'Not ordered', sent: 'Sent to Valio', ready: 'Ready to order' },
  result: {
    aria: 'Agent result',
    orderedFor: (d: string) => `Ordered for ${d}.`,
    frontDoor: (s: string) => `Sent to Valio’s front door: ${DOOR_STATUS[s] ?? s.replace(/_/g, ' ')}.`,
    seeHistory: 'See it in History',
    rejected: 'Rejected. Nothing was ordered.',
    of: (amount: string, name: string) => `${amount} of ${name}`,
    products: (n: number) => `${n} products`,
    exclVat: 'excl. VAT',
    forBoth: ' for both',
    arrives: (days: number, weekdayName: string, date: string) =>
      days === 0 ? 'Arrives today.' : days === 1 ? 'Arrives tomorrow.' : days > 1 && days < 8 ? `Arrives ${weekdayName}, in ${days} days.` : `Arrives ${date}.`,
    signOff: (who: string | null, approved: boolean, time: string) => `${who ?? 'You'} ${approved ? 'approved' : 'rejected'} · ${time}`,
    done: 'Ordered ✓',
    approve: (m: string) => `Approve · ${m}`,
    approving: 'Approving…',
    reject: 'Reject',
    rejecting: 'Rejecting…',
    needKey: 'Add your approver key under Keys to approve.',
    orderBoth: (two: boolean, m: string) => `${two ? 'Order both' : 'Order these'} · ${m}`,
    ordering: 'Ordering…',
    orderIt: (m: string) => `Order it · ${m}`,
    notThis: 'Not this one',
    decidedBy: (rule: string) => `Decided by ${rule}.`,
    ruleWords: {
      AUTO: 'your rules: within every limit', SPEND_OVER_LIMIT: 'your order limit', LINE_OVER_CAP: 'your per-product limit',
      WEEKLY_BUDGET_EXCEEDED: 'your weekly budget', ALLERGEN_CONTAINS: 'your allergen rule', ALLERGEN_MAY_CONTAIN: 'your allergen rule',
      ALLERGEN_DATA_MISSING: 'missing allergen data', BLOCKLISTED: 'your blocked products', LOW_CONFIDENCE: 'the Gemini match check',
      LOW_RELIABILITY: 'your on-time rule', STOCK_NONE: 'Valio’s stock', STOCK_PARTIAL: 'Valio’s stock', CUTOFF_PASSED: 'Valio’s order cut-off',
      DATE_NOT_HONOURED: 'Valio’s delivery days', QTY_AMBIGUOUS: 'an unclear amount', QTY_SUSPICIOUS: 'an unusual amount',
      QTY_UNKNOWN: 'an unclear amount', PRICE_CHANGED: 'a price change', PRICE_MISSING: 'a missing price', UNKNOWN_PRODUCT: 'the catalogue',
      MANDATE_MISSING: 'missing rules', MANDATE_EXPIRED: 'rules that have ended', PROFILE_DEFAULT: 'your kitchen profile',
      UNDELIVERABLE: 'Valio’s delivery', DATA_MISSING: 'missing data',
    } as Record<string, string>,
    colProduct: 'Product',
    colAmount: 'Amount',
    colPrice: 'Unit price',
    colTotal: 'Total',
    delivery: 'Delivery',
    pickOne: 'Pick one',
    approveSelected: (m: string) => `Approve selected · ${m}`,
    orderSelected: (m: string) => `Order selected · ${m}`,
    changeQty: 'Change quantity',
    newAmount: 'New amount',
    askAgain: 'Ask again',
    decline: 'Decline',
    tagBest: 'Best match',
    tagCheaper: 'Cheaper',
    tagLocal: 'Local',
    safer: 'Safe alternatives',
    compare: (n: number) => `Compare options (${n})`,
    compareTitle: 'Compare options',
    compareClose: 'Close',
    cmp: {
      price: 'Unit price', total: 'Total', arrives: 'Arrives', orderBy: 'Order by', stock: 'Stock', onTime: 'On time',
      origin: 'Origin', co2: 'CO₂ per kg', match: 'Match', diet: 'Labels', allergens: 'Allergens',
    },
    notReported: 'not reported',
    noneListed: 'none listed',
    mayContain: (a: string) => `may contain ${a}`,
    co2Value: (kg: string) => `${kg} kg CO₂e`,
    choose: 'Choose this',
    approveThis: 'Approve this',
    rememberQ: (name: string) => `Remember ${name} for next time?`,
    rememberOrder: 'This order only',
    rememberAlways: 'Always',
    rememberNo: 'Not now',
    addSpare: (amount: string, cost: string) => `Add ${amount} spare (+${cost})`,
    remembered: (scope: string): string => (scope === 'always' ? 'Remembered. You can revoke it in Rules, under What I know about your kitchen.' : 'Remembered for this order.'),
    whyThis: (query: string) => `Why this ${query}`,
    why: (name: string) => `Why ${name}`,
    neededOk: 'Why it needed your OK',
    also: (n: number) => `Also worth knowing (${n})`,
    other: (n: number) => `Other options (${n})`,
    understood: 'What the agent understood',
    split: (have: string, rest: string, extra: string) => `Valio has ${have}. Top up with ${rest} ${extra}?`,
    splitFallback: 'Valio can cover it with a substitute.',
    splitAria: 'The split order',
    inTotal: 'in total',
    substitute: '(substitute)',
    notQuoted: 'Valio didn’t quote this.',
    stockUnknown: 'Stock not confirmed',
    orderBy: (t: string) => `order by ${t}`,
    arrivesOn: (d: string) => `arrives ${d}`,
    onTime: (p: number) => `On time for ${p}% of deliveries.`,
    from: (c: string) => `From ${c}.`,
    co2: (v: string) => `${v} kg CO₂e per kg.`,
    per: (p: string, unit: string) => ` ${p} per ${unit}.`,
    orderInstead: 'Choose this',
    usual: 'You usually order this',
    plainInstead: (need: string) => `Not ${need} this time`,
    checkThis: 'Check this: not in the order yet.',
    addToOrder: 'Add to the order',
    added: 'Added to the order.',
    askFor: 'Ask for this instead',
    keysFirst: 'Enter your keys first (Keys, at the top).',
    otherChoices: 'Other choices Valio has',
    rank: { best: 'Best match', better: 'Good match', good: 'Also works' } as Record<string, string>,
    perUnit: (unit: string) => `per ${unit}`,
    onTimeShort: (p: number) => `${p}% on time`,
  },
  menu: {
    aria: 'Proposed cart',
    forGuests: (n: string) => `for ${n} guests`,
    forMenu: 'for your menu',
    cart: (who: string, m: string) => `A cart ${who}, ${m}.`,
    announce: (who: string, m: string) => `Ready to order. A cart ${who}, ${m}.`,
    sub: (d: string) => `Portions are estimates. Check them before you order. Delivery ${d}, prices excl. VAT.`,
    summary: (who: string) => `Menu ${who}`,
    theCart: 'The cart',
    forDishes: (dishes: string[]) =>
      `For ${dishes.length < 2 ? dishes.join('') : `${dishes.slice(0, -1).join(', ')} and ${dishes[dishes.length - 1]}`}`,
    noConfident: 'No confident match, so nothing is in the cart for this. See the options.',
    nothingFits: 'Nothing on Valio’s list fits this.',
    amountUnclear: 'Amount unclear',
    orderCart: (m: string) => `Order this cart · ${m}`,
    amounts: 'Amounts per cover',
    ingredients: (n: number) => `${n} ${plural(n, 'ingredient', 'ingredients')}`,
    perCover: (a: string) => `${a} per cover`,
    perPortion: (unit: string) => `${unit} per portion`,
    portionAria: (ingredient: string, dish: string) => `${ingredient} per portion in ${dish}`,
    yours: 'your portion',
    updating: 'Updating the cart…',
    undoPortions: 'Undo',
    youHave: (matched: string, thisOrder: boolean) => `You have this (${matched}${thisOrder ? ', this order only' : ''}), so it's left out.`,
    addAnyway: 'Add anyway',
    addAnywayOn: 'Will be added: Update the cart',
    coverage: (total: string, inCart: number, all: number, check: number, checkTotal: string, have: number) =>
      [`${total} for ${inCart} of ${all} ingredients`, have > 0 && `${have} you already have`, check > 0 && `${check} need your look, about ${checkTotal}`].filter(Boolean).join('; ') + '.',
    update: (n: number) => `Update the cart (${n} ${n === 1 ? 'change' : 'changes'})`,
    spareLine: (needed: string, pct: string) => `Needed ${needed}, plus ${pct}% spare`,
    spareCost: (m: string) => `(${m} beyond what the recipe needs)`,
    spareAria: (ingredient: string) => `Spare for ${ingredient}, in percent`,
    spareUnit: '% spare',
    spareTotal: (pct: string, m: string, rounding: string) => `Includes about ${pct}% spare for kitchen loss, about ${m}; ${rounding}% of it is pack rounding.`,
    step1: 'Your menu',
    step1Sub: (guests: string | null, day: string) => [guests && `${guests} guests`, `delivery ${day}`].filter(Boolean).join(', ') + '.',
    step2: 'Portions per dish',
    step2Sub: 'Estimates from the recipe, per cover and in total. Check them before you order.',
    step3Sub: (m: string) => `${m} excl. VAT. Swap any product, then order the cart.`,
  },
  rules: {
    title: 'Your rules',
    intro: 'What the agent follows on every order. Valio’s front door checks them again.',
    needKey: 'Add your approver key under Keys to see and change your rules.',
    know: 'What I know about your kitchen',
    knowNote: 'From your kitchen’s profile. The agent uses it as guidance, never as a rule.',
    knowDiet: 'Always',
    knowUsual: (n: number) => `${n} product${n === 1 ? '' : 's'} you usually order`,
    knowNothing: 'Nothing yet. It learns from your confirmed orders.',
    knowFailed: 'Couldn’t load your kitchen’s profile.',
    scope: { always: 'always', this_order: 'this order only' } as Record<string, string>,
    revoke: 'Revoke',
    revoking: 'Revoking…',
    updateKitchen: 'Update my kitchen',
    revokeNeedsKey: 'Add your approver key under Keys to revoke a remembered preference.',
    loadFailed: 'Couldn’t load your rules.',
    loading: 'Loading your rules…',
    none: 'No rules yet. Until you add some, the agent asks you about every order.',
    youSaid: (t: string) => `You said: “${t}”`,
    tell: 'Tell the agent your rules',
    tellHelp: 'Write them the way you’d tell a new cook. Anything you leave out goes back to the safe default.',
    placeholder: 'Never anything with peanuts. Order on your own up to €1,500; above that, ask me.',
    nothingChanges: 'Nothing changes until you save.',
    check: 'Check the changes',
    reading: 'Reading…',
    readingLong: 'Reading your rules and comparing them with the ones in force…',
    readingAnnounce: 'Reading your rules…',
    changes: (n: number) => (n ? `${n} ${plural(n, 'change', 'changes')} to your rules.` : 'No changes to your rules.'),
    notSaved: 'Not saved yet',
    changesAnnounce: (n: number) => `${n} ${plural(n, 'change', 'changes')} to your rules. Not saved yet.`,
    injectionTitle: 'Part of this reads like an instruction to the agent, not a rule.',
    injectionBody: 'Check where the text came from before you save.',
    fallback: 'These rules couldn’t be read, so nothing would change. Write them as short, plain sentences and check again.',
    before: 'Before you save',
    skipped: (q: string) => `Skipped: ${q}`,
    undo: 'Undo',
    skip: 'Skip',
    addAnswers: 'Add my answers and check again',
    assumed: (n: number) => `What the agent assumed (${n})`,
    sure: 'Are you sure?',
    yesSave: 'Yes, save these rules',
    goBack: 'Go back',
    save: 'Save rules',
    saving: 'Saving…',
    discard: 'Discard',
    answerFirst: 'Answer or skip the questions above first.',
    saved: (n: number) => (n ? `Saved. ${n} ${plural(n, 'change', 'changes')} to your rules.` : 'Saved. Your rules are the same as before.'),
    savedStatus: 'Saved',
    savedSub: 'The agent uses them from the next order. The change is in History.',
    savedAnnounce: 'Rules saved.',
    conflict: 'Someone changed these rules a moment ago. Here’s the latest.',
    conflictSub: 'Your text is still in the box: check the changes again, then save.',
  },
  history: {
    title: 'History',
    refresh: 'Refresh',
    loading: 'Loading…',
    needKey: 'Add your approver key under Keys to see the history.',
    loadFailed: 'Couldn’t load the history.',
    empty: 'Nothing yet. Your first order will show up here.',
    today: 'Today',
    yesterday: 'Yesterday',
    recently: 'Recently',
    all: 'All history',
    yourRules: 'Your rules',
    step: {
      approved: (who: string) => `${who} approved it`,
      rejected: (who: string) => `${who} rejected it`,
      rulesChanged: (who: string) => `${who} changed the rules`,
      agentSent: 'The agent sent it to Valio',
      agentDeclined: 'The agent didn’t order it',
      agentAsked: 'The agent asked you first',
      valioConfirmed: 'Valio confirmed it',
      valioRefused: 'Valio refused it',
      valioHeld: 'Valio held it for your OK',
    },
    outcome: {
      ordered: 'Ordered', rejected: 'Rejected', rules: 'Rules changed', notOrdered: 'Not ordered', held: 'Held for your OK',
      sent: 'Sent to Valio', needed: 'Needed your OK',
    },
  },
  kitchen: {
    signedIn: (name: string) => `Signed in as ${name}`,
    switch: 'Switch kitchen',
  },
  conv: {
    field: 'Message the agent',
    placeholder: 'Ask for an order, or paste a menu',
    answerHere: 'Type your answer',
    voicePlaceholder: 'Type while talking',
    send: 'Send',
    mute: 'Mute the microphone',
    unmute: 'Unmute the microphone',
    end: 'End voice',
    voice: 'Talk to the agent',
    showThread: 'Show the conversation',
    voiceOnly: 'Voice only',
    orbToThread: 'Show the conversation',
    orbToBig: 'Voice only',
    muted: 'Microphone off.',
    folded: (status: string, what: string) => `${status}: ${what}`,
    pantryRead: (items: string) => `I can see you have: ${items}. I'll leave those out of your next menu cart.`,
    cartNow: (total: string) => `Cart updated: ${total}. Check the assumptions before ordering.`,
    open: 'Open',
  },
  talk: {
    open: 'Talk',
    title: 'Talk to the agent',
    connecting: 'Connecting…',
    state: { listening: 'Listening…', thinking: 'Checking…', speaking: 'Speaking…', error: 'Stopped.', connecting: 'Connecting…' } as Record<string, string>,
    end: 'End',
    you: 'You',
    agent: 'Agent',
    closed: 'The conversation ended. Tap Talk to start again.',
    denied: 'The microphone is blocked. Allow it in the browser’s site settings, or type instead.',
  },
  photo: {
    label: 'Order from a photo of a note, a menu or a slip',
    short: 'Photo',
    reading: 'Reading your photo…',
    read: 'Read',
    unreadable: (what: string) => `Couldn’t read: ${what}`,
    nothing: 'No words could be read from that photo. Try a sharper one, or type it.',
    close: 'Close',
    ignored: 'This photo contained an instruction, which was ignored. Only the list itself was read.',
  },
  valio: {
    nav: 'Valio',
    open: 'Valio view',
    keyTitle: 'Valio view',
    keyIntro: 'For Valio Aimo’s operations team: every kitchen’s orders and decisions, read-only.',
    key: 'Valio admin key',
    keyHelp: 'Read-only. It can’t order or approve anything.',
    open2: 'Open the Valio view',
    forget: 'Forget the admin key',
    title: 'Valio view',
    intro: 'Every kitchen’s requests and what the front door decided. Read-only.',
    buyer: 'Kitchen',
    allBuyers: 'All kitchens',
    show: 'Show',
    shows: { all: 'Everything', confirmed: 'Ordered', pending_approval: 'Held for the chef’s OK', refused: 'Refused', rejected: 'Rejected by the chef', ASK_HUMAN: 'Agent asked first', DECLINE: 'Not ordered', security: 'Security events' } as Record<string, string>,
    refresh: 'Refresh',
    loading: 'Loading…',
    empty: 'Nothing matches.',
    loadFailed: 'Couldn’t load the trail.',
    requests: (n: number) => `${n} request${n === 1 ? '' : 's'}`,
    security: 'Security',
    securityIntro: 'Refused attempts. Key values are never recorded.',
    event: {
      invalid_key: (h: string) => `A key that isn’t valid was refused${h ? ` (${h})` : ''}.`,
      key_used_outside_its_role: (h: string) => `A real key was used where it isn’t allowed${h ? ` (${h})` : ''}.`,
      cross_buyer_attempt: () => 'Tried to act on another kitchen’s order.',
      client_sent_mandate: () => 'A client tried to send its own rules. They were ignored.',
      bad_request_signature: () => 'A request with a bad signature was refused.',
    } as Record<string, (h: string) => string>,
    unknownEvent: (e: string) => `Refused: ${e.replace(/_/g, ' ')}.`,
    by: (who: string) => `by ${who}`,
    route: (r: string) => `on ${r}`,
    suppressed: (n: number) => `${n} more like this were counted, not listed.`,
    verify: 'Check the signature',
    verifying: 'Checking…',
    signed: 'Signed by the front door ✓',
    notSigned: 'Not signed by this front door',
  },
  voice: {
    mic: 'Order by voice: hold to talk, or press to start and again to send',
    stop: 'Stop and send',
    intro: 'Hold to order by voice. Audio is only used to transcribe this request.',
    start: 'Start talking',
    notNow: 'Not now',
    hold: 'Listening… let go to send.',
    toggle: 'Listening… tap the mic to send.',
    thinking: 'Thinking…',
    blocked: 'The microphone is blocked. You can type instead, or allow it in the browser’s site settings.',
    failed: 'Couldn’t start the microphone. You can type instead.',
    readOn: 'Read aloud.',
    readOff: 'Read-back is off.',
    mute: 'Mute',
    turnOn: 'Turn on',
  },
  progress: {
    aria: 'What the agent is doing',
    dropped: 'The connection dropped before the answer came back. Check History before asking again, in case it was ordered.',
    phases: {
      understanding: 'Reading your request…',
      planning: 'Turning the menu into ingredients…',
      searching: 'Searching Valio’s catalogue…',
      stock: 'Checking Valio stock and prices…',
      judging: 'Asking Gemini to double-check each match…',
      ordering: 'Placing the order at Valio’s front door…',
    } as Record<string, string>,
  },
  urgent: {
    title: 'Need it sooner?',
    note: 'Suggestions only. The agent hasn’t ordered any of these.',
    walkIn: 'Pick it up yourself now',
    hours: (opens: string, closes: string, open: boolean) => `Today ${opens}–${closes}, ${open ? 'open now' : 'closed now'}.`,
    call: (phone: string) => `Stock isn’t confirmed online. Call ${phone} before you go.`,
    clickCollect: 'Click & Collect (Helsinki only)',
    ready: (at: string | null) =>
      `Ready from about 4 hours after you confirm${at ? ` (around ${at} if you confirm now)` : ''}. Ordered on Valio’s own site; the agent doesn’t place pickup orders.`,
    nextDelivery: 'Next delivery',
    earliest: (d: string, cutoff: string | null) => `The earliest Valio delivery is ${d}${cutoff ? `, if ordered by ${cutoff}` : ''}.`,
  },
}
