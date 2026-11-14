// Everything the chef reads that isn't data lives here, so wording can be tuned in one place.
// Voice: a calm colleague. Short sentences, plain words, the number that matters, no system-speak.
import { flagLabel, formatCents, formatDateTime, formatDay, formatEuro, stockText } from './format'
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
  PS: 'bag', BAG: 'bag', RAS: 'box', RS: 'tray', PLO: 'bottle', TLK: 'tin', KRT: 'carton',
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
  lang: { switchTo: 'Suomeksi', short: 'FI', label: 'Kieli: suomi' }, // the switch offers the other language, in that language
  greeting: (part: 'morning' | 'afternoon' | 'evening', name: string | null, waiting: number) =>
    `${{ morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening' }[part]}${name ? `, ${name}` : ''}. ` +
    (waiting === 0 ? 'Nothing waiting for you.' : `${waiting} ${plural(waiting, 'order is', 'orders are')} waiting for your OK in History.`),
  offline: {
    title: 'Can’t reach the ordering service.',
    body: 'Your request will fail until it’s back. If you run it yourself, start the backend on port 8000.',
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
    show: 'Show',
    hide: 'Hide',
  },
  status: { ordered: 'Ordered', yourCall: 'Your call', rejected: 'Rejected', notOrdered: 'Not ordered', sent: 'Sent to Valio', ready: 'Ready to order' },
  result: {
    aria: 'Agent result',
    orderedFor: (d: string) => `Ordered for ${d}.`,
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
    orderInstead: 'Order this instead',
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
  },
  rules: {
    title: 'Your rules',
    intro: 'What the agent follows on every order. Valio’s front door checks them again.',
    needKey: 'Add your approver key under Keys to see and change your rules.',
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
    fallback: 'Gemini wasn’t available, so a simpler reader was used. Check the changes carefully.',
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
