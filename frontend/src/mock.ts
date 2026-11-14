import { ApiError } from './api'
import type {
  InterviewAnswer,
  InterviewNextResponse,
  InterviewPreview,
  KitchenHistory,
  KitchenLiveEvent,
  StandingOrder,
  StandingOrderLine,
  StandingOrderUpdate,
  Weekday,
} from './kitchenEditApi'
import type { Saved } from './onboardingApi'
// Mock backend for VITE_MOCK=1 / ?mock=1 (dev only). Products are real catalogue entries; prices,
// stock and cut-offs are illustrative. Which fixture you get depends on the request text:
//   contains "1000" / "1 000" / "1,000"  -> ASK_HUMAN, order pending_approval (the lactose-free milk case)
//   contains "cream" or "tomorrow"       -> refused at the front door (cut-off passed)
//   contains "stock" or "split"          -> refused for partial stock, with substitutes + a split order proposal
//   contains "error"                     -> a failed request (to see the error state)
//   anything else                        -> AUTO, order confirmed (small butter order)
import type {
  AdminFilter, AdminRow, BuyerProfile, KitchenContext, LiveSocket, PhotoRead, SecurityEvent, AgentRun, Alternative, AlternativeOrder, AuditEntry, Decision, Health, Line, OrderInput, OrderResponse, OrderStatus,
  AskInput, AskResponse, CompileResult, Mandate, MenuInput, MenuRun, Product, RuleChange, SaveResult, Quote, QuantityResolution, Reason, RunInput, Substitute,
} from './types'
import type { CalendarDay, CalendarEntry, CalendarLine, CalendarResponse, WeeklyMenu } from './calendarApi'

const NOW = '2026-11-14T10:00:00+00:00'

const product = (p: Partial<Product> & Pick<Product, 'id' | 'name_en' | 'sales_unit'>): Product => ({
  name_fi: null,
  brand: 'Valio',
  claims: ['FREE_FROM_LACTOSE'],
  allergens: { contains: ['AM'], may_contain: [], free_from: [] },
  delivery_reliability: null,
  carbon_kg_per_kg: 1.1,
  ...p,
})

const quote = (q: Partial<Quote> & Pick<Quote, 'product_id'>): Quote => ({
  logistic_model: 'Stock',
  available_amount: null,
  quantity_known: true,
  available_date: '2026-11-16',
  order_cutoff: null,
  sales_unit: 'ST',
  price: null,
  price_with_tax: null,
  comparison_price: null,
  comparison_unit: null,
  flags: [],
  orderable: true,
  fetched_at: NOW,
  ...q,
})

const qty = (
  product_id: string, amount: number, unit: string, sales_unit: string, quantity: number, per: number, explanation: string,
  extra: Partial<QuantityResolution> = {},
): QuantityResolution => ({
  product_id, requested: { amount, unit }, sales_unit, quantity, per_sales_unit: per, delivered: quantity * per,
  over_delivery: quantity * per - amount, rounded_up: false, confidence: 'high', needs_confirmation: false, explanation,
  ...extra,
})

const reason = (code: string, severity: Reason['severity'], message: string, r: Partial<Reason> = {}): Reason => ({
  code, severity, message, facts: {}, suggested_fix: null, product_id: null, ...r,
})

const decision = (
  outcome: Decision['outcome'], reasons: Reason[], alternatives: Alternative[] = [], confidence: number | null = null,
): Decision => ({
  contract_version: '0.2', request_id: 'req-mock', outcome, reasons, primary_reason: reasons[0] ?? null,
  confidence, alternatives, rules_version: 'mock', decided_at: NOW,
})

type Fixture = {
  request: AgentRun['request']
  lines: Line[]
  decision: Decision // the front door's decision (or the agent's, when no order is placed)
  agent?: Decision // the agent's own decision when it differs (e.g. AUTO, then the door asks)
  status: OrderStatus | null // null: the agent asked first, so nothing went to the door
  substitutes?: Substitute[]
  alternative_order?: AlternativeOrder | null
}

const MILK: Fixture = {
  request: {
    summary: '1000 L lactose-free milk, delivered Monday 16 Nov',
    items: [{ query: 'lactose-free milk', amount: 1000, unit: 'L', claims: ['FREE_FROM_LACTOSE'], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({
        id: '463335', name_en: 'Valio Eila® 3 % milk drink 1 l lactose free',
        name_fi: 'Valio Eila® 3 % maitojuoma 1 l laktoositon', sales_unit: 'ST', delivery_reliability: 1.0,
      }),
      quote: quote({
        product_id: '463335', price: 1.56, comparison_price: 1.56, comparison_unit: 'L', available_amount: 9999999999, // Valio's "plenty"
        order_cutoff: '2026-11-15T13:00:00+02:00',
      }),
      quantity: qty('463335', 1000, 'L', 'ST', 1000, 1, '1,000 L ÷ 1 L per ST (1 LTR per ST) = 1,000 ST.'),
      line_total_cents: 156000,
      why: 'Lactose free, 1 l cartons in stock for Monday, best delivery reliability (100 %).',
      chosen: true,
      confidence: 0.959, // floors to 0.95, as the backend does
      confidence_reason: 'Lactose-free milk in 1 l cartons: exactly what the request asks for.',
      facts: { delivery_reliability: 1.0, carbon_kg_per_kg: 1.1, origin: 'fi' },
    },
    {
      product: product({ id: '462775', name_en: 'Arla Milkdrink 1L lactose free fat free UHT Suomesta', brand: 'Arla', sales_unit: 'ST' }),
      quote: quote({ product_id: '462775', price: 1.25, comparison_price: 1.25, comparison_unit: 'L', available_amount: 2000 }),
      quantity: qty('462775', 1000, 'L', 'ST', 1000, 1, '1,000 L ÷ 1 L per ST (1 LTR per ST) = 1,000 ST.'),
      line_total_cents: 125000,
      why: 'Cheapest, but a fat-free UHT milk drink rather than milk.',
      chosen: false,
      confidence: 0.76,
      confidence_reason: 'A fat-free UHT "milk drink", not the fresh milk a kitchen usually means by "milk".',
      facts: { delivery_reliability: 0.947, carbon_kg_per_kg: 1.0, origin: 'fi' },
    },
    {
      product: product({ id: '463038', name_en: 'Valio Eila® semi skimmed milk drink 10 l novobox lactose free', sales_unit: 'KI' }),
      quote: quote({
        product_id: '463038', logistic_model: 'Terminal', sales_unit: 'KI', price: 13.2, comparison_price: 0.66,
        comparison_unit: 'L', quantity_known: false, order_cutoff: '2026-11-12T15:00:00+02:00',
        flags: ['quantity_unknown', 'cutoff_passed'], orderable: false,
      }),
      quantity: qty('463038', 1000, 'L', 'KI', 50, 20, '1,000 L ÷ 20 L per KI (10 LTR per ST × 2 ST per KI) = 50 KI. Please confirm: assumes the recorded volume is per ST, not per whole KI.', { confidence: 'medium', needs_confirmation: true }),
      line_total_cents: 66000,
      why: 'Cheaper per litre, but the order deadline for Monday has passed.',
      chosen: false,
    },
  ],
  decision: decision(
    'ASK_HUMAN',
    [
      reason('SPEND_OVER_LIMIT', 'ASK_HUMAN', 'This order is €1,560.00 (net of VAT), above your €1,500.00 auto-approve limit.', {
        suggested_fix: 'Approve, reduce the quantity to fit the limit, or reject.', facts: { total_cents: 156000, limit_cents: 150000 },
      }),
    ],
    [{ product_id: '462775', summary: 'Arla lactose-free milk drink 1 l is cheaper, but Gemini rates it 0.76 as a match for "milk".' }],
    0.96,
  ),
  agent: decision('AUTO', [], [], 0.95),
  status: 'pending_approval',
}

// The demo's other moment: the cheapest match is a 'milk drink', and Gemini isn't sure that's what was meant.
const DRINK: Fixture = {
  request: {
    summary: '200 L milk drink, delivered Monday 16 Nov',
    items: [{ query: 'milk drink', amount: 200, unit: 'L', claims: [], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({ id: '462775', name_en: 'Arla Milkdrink 1L lactose free fat free UHT Suomesta', brand: 'Arla', sales_unit: 'ST' }),
      quote: quote({ product_id: '462775', price: 1.25, comparison_price: 1.25, comparison_unit: 'L', available_amount: 2000 }),
      quantity: qty('462775', 200, 'L', 'ST', 200, 1, '200 L ÷ 1 L per ST (1 LTR per ST) = 200 ST.'),
      line_total_cents: 25000,
      why: 'The closest match for "milk drink", in stock for Monday.',
      chosen: true,
      confidence: 0.72,
      confidence_reason: 'A fat-free UHT drink; "milk drink" could also mean the regular Eila drink.',
      facts: { delivery_reliability: 0.947, carbon_kg_per_kg: 1.0, origin: 'fi' },
    },
    {
      product: product({ id: '463335', name_en: 'Valio Eila® 3 % milk drink 1 l lactose free', sales_unit: 'ST', delivery_reliability: 1.0 }),
      quote: quote({ product_id: '463335', price: 1.56, comparison_price: 1.56, comparison_unit: 'L', available_amount: 2400 }),
      quantity: qty('463335', 200, 'L', 'ST', 200, 1, '200 L ÷ 1 L per ST (1 LTR per ST) = 200 ST.'),
      line_total_cents: 31200,
      why: 'The regular Eila milk drink, in stock for Monday.',
      chosen: false,
      confidence: 0.69,
      confidence_reason: 'A milk drink, but the request didn’t say lactose free.',
      facts: { delivery_reliability: 1.0, carbon_kg_per_kg: 1.1, origin: 'fi' },
    },
  ],
  decision: decision(
    'ASK_HUMAN',
    [
      reason('LOW_CONFIDENCE', 'ASK_HUMAN', 'Not sure that Arla Milkdrink 1L lactose free fat free UHT is right (0.72 vs your 0.80 threshold). A fat-free UHT drink; "milk drink" could also mean the regular Eila drink.', {
        product_id: '462775', suggested_fix: 'Confirm the product and quantity, or pick an alternative.', facts: { confidence: 0.72, threshold: 0.8 },
      }),
    ],
    [],
    0.72,
  ),
  status: null,
}

// A kebab shop's order: no guests, no menu, just meat for the rotisserie. (Product invented for the demo.)
const DONER: Fixture = {
  request: {
    summary: '20 kg döner kebab meat, delivered Friday',
    items: [{ query: 'döner kebab meat', amount: 20, unit: 'kg', claims: [], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({ id: '480001', name_en: 'Döner kebab meat cone beef & chicken 10 kg frozen', brand: 'Valio Aimo', sales_unit: 'ST', claims: [], allergens: { contains: ['AW', 'AY'], may_contain: [], free_from: [] }, delivery_reliability: 0.97 }),
      quote: quote({ product_id: '480001', price: 64.9, comparison_price: 6.49, comparison_unit: 'KG', available_amount: 120, sales_unit: 'ST' }),
      quantity: qty('480001', 20, 'kg', 'ST', 2, 10, '20 kg ÷ 10 kg per ST = 2 ST.'),
      line_total_cents: 12980,
      why: 'A 10 kg cone for the rotisserie, frozen, in stock for Friday.',
      chosen: true,
      confidence: 0.94,
      confidence_reason: 'A döner meat cone for a rotisserie: exactly what the request asks for.',
      facts: { delivery_reliability: 0.97, carbon_kg_per_kg: 14.2, origin: 'de' },
    },
  ],
  decision: decision('AUTO', [], [], 0.94),
  status: 'confirmed',
}

const BUTTER: Fixture = {
  request: {
    summary: '10 kg unsalted butter, delivered Monday 16 Nov',
    items: [
      { query: 'unsalted butter', amount: 10, unit: 'kg', claims: [], exclude_allergens: [] },
      { query: 'fresh herbs', amount: null, unit: null, claims: [], exclude_allergens: [] },
    ],
  },
  lines: [
    {
      product: product({ id: '464411', name_en: 'Valio butter 500 g unsalted', sales_unit: 'ST', claims: [], delivery_reliability: 1.0 }),
      quote: quote({
        product_id: '464411', price: 4.85, comparison_price: 9.7, comparison_unit: 'KG', available_amount: 640,
        order_cutoff: '2026-11-15T13:00:00+02:00',
      }),
      quantity: qty('464411', 10, 'kg', 'ST', 20, 0.5, '10 kg ÷ 0.5 kg per ST (500 GRM per ST) = 20 ST.'),
      line_total_cents: 9700,
      why: 'Exact match (unsalted, 500 g), in stock for Monday.',
      chosen: true,
    },
    {
      product: product({ id: '467000', name_en: 'Fresh herbs', sales_unit: 'ST', claims: [] }),
      quote: quote({ product_id: '467000', price: 2.5 }),
      quantity: null,
      line_total_cents: null,
      why: 'The request did not include an amount.',
      chosen: false,
    },
  ],
  decision: decision('AUTO', []),
  status: 'confirmed',
}

const CREAM: Fixture = {
  request: {
    summary: '40 L lactose-free whipping cream, delivered tomorrow (Sun 15 Nov)',
    items: [{ query: 'whipping cream', amount: 40, unit: 'L', claims: ['FREE_FROM_LACTOSE'], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({ id: '464194', name_en: 'Valio whipping cream 1 l UHT lactose free', sales_unit: 'ST', delivery_reliability: 1.0 }),
      quote: quote({
        product_id: '464194', price: 4.35, comparison_price: 4.35, comparison_unit: 'L', available_amount: 300,
        order_cutoff: '2026-11-13T15:00:00+02:00', available_date: '2026-11-17', flags: ['cutoff_passed'], orderable: false,
      }),
      quantity: qty('464194', 40, 'L', 'ST', 40, 1, '40 L ÷ 1 L per ST (1 LTR per ST) = 40 ST.'),
      line_total_cents: 17400,
      why: 'Best match, but it cannot arrive on Sunday 15 Nov.',
      chosen: true,
    },
  ],
  decision: decision(
    'ASK_HUMAN',
    [
      reason('CUTOFF_PASSED', 'ASK_HUMAN', 'The order cut-off for Valio whipping cream 1 l UHT lactose free (2026-11-13T15:00:00+02:00) has passed, so it can\'t be ordered for 2026-11-15.', {
        product_id: '464194', suggested_fix: 'Pick an alternative that can still arrive, or a later delivery date.',
        facts: { closing_time: '2026-11-13T15:00:00+02:00' },
      }),
      reason('DATE_NOT_HONOURED', 'ASK_HUMAN', 'Valio whipping cream 1 l UHT lactose free arrives 2026-11-17, not 2026-11-15.', {
        product_id: '464194', suggested_fix: 'Accept the later date or pick an alternative.',
      }),
    ],
    [{ product_id: '461273', summary: 'Valio whipping cream 20 l novobox lactose free (2 boxes), delivered Tue 17 Nov.' }],
  ),
  status: 'refused',
  substitutes: [
    {
      product_id: '464699', replaces: '464194', tier: 'best', name: 'Valio whipping cream 1 l lactose free, organic',
      why_safe: 'Same category (cream), lactose free like the original, no allergens you excluded.',
      unit: 'ST', unit_price_cents: 590, reliability: 0.947, origin: 'fi', available: null,
    },
    {
      product_id: '461273', replaces: '464194', tier: 'better', name: 'Valio whipping cream 20 l novobox lactose free',
      why_safe: 'Same cream, lactose free, sold in 20 l boxes.', unit: 'KI', unit_price_cents: 8200, reliability: 1.0,
      origin: 'fi', available: 12,
    },
    {
      product_id: '466012', replaces: '464194', tier: 'good', name: 'Arla cooking cream 15 % 1 l lactose free',
      why_safe: 'Lactose free, but a cooking cream: it will not whip.', unit: 'ST', unit_price_cents: 310,
      reliability: 0.88, origin: 'se', available: 400,
    },
  ],
}

const SHORT: Fixture = {
  request: {
    summary: '1000 × 500 g unsalted butter, delivered Monday 16 Nov',
    items: [{ query: 'unsalted butter 500 g', amount: 1000, unit: 'pcs', claims: [], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({ id: '464411', name_en: 'Valio butter 500 g unsalted', sales_unit: 'ST', claims: [], delivery_reliability: 1.0 }),
      quote: quote({ product_id: '464411', price: 4.85, comparison_price: 9.7, comparison_unit: 'KG', available_amount: 640 }),
      quantity: qty('464411', 1000, 'pcs', 'ST', 1000, 1, '1,000 pcs = 1,000 ST (1 piece = 1 ST).'),
      line_total_cents: 485000,
      why: 'Exact match, but only 640 in stock.',
      chosen: true,
      confidence: 0.98,
      confidence_reason: 'Unsalted butter in 500 g packs, as asked.',
      facts: { delivery_reliability: 1.0, carbon_kg_per_kg: 9.6, origin: 'fi' },
    },
  ],
  decision: decision(
    'ASK_HUMAN',
    [
      reason('STOCK_PARTIAL', 'ASK_HUMAN', 'Only 640 ST of Valio butter 500 g unsalted available, 1000 ordered.', {
        product_id: '464411', suggested_fix: 'Reduce to 640 and cover the rest with an alternative.',
        facts: { available: 640, requested: 1000 },
      }),
    ],
    [],
    0.98,
  ),
  status: 'refused',
  substitutes: [
    {
      product_id: '464420', replaces: '464411', tier: 'best', name: 'Valio butter 500 g unsalted, organic',
      why_safe: 'Same category (butter), unsalted, same 500 g pack.', unit: 'ST', unit_price_cents: 595,
      reliability: 0.98, origin: 'fi', available: 900,
    },
    {
      product_id: '466731', replaces: '464411', tier: 'good', name: 'Lurpak butter 500 g unsalted',
      why_safe: 'Unsalted butter, 500 g, no allergens you excluded.', unit: 'ST', unit_price_cents: 640,
      reliability: null, origin: 'dk', available: null,
    },
  ],
  alternative_order: {
    lines: [
      { product_id: '464411', name: 'Valio butter 500 g unsalted', quantity: 640, unit: 'ST', unit_price_cents: 485, line_total_cents: 310400 },
      {
        product_id: '464420', name: 'Valio butter 500 g unsalted, organic', quantity: 360, unit: 'ST', unit_price_cents: 595,
        line_total_cents: 214200, replaces: '464411',
      },
    ],
    total_cents: 524600,
    summary: 'Split across products: 640 ST of Valio butter 500 g unsalted + 360 ST of Valio butter 500 g unsalted, organic (best substitute). New total €5,246.00 net; needs your approval, then order these lines.',
  },
}

let seq = 0
const audit: AuditEntry[] = []
const wait = () => new Promise((r) => setTimeout(r, 600))

function log(actor: string, buyer_id: string, text: string, d: Decision): string {
  const id = `aud-mock-${++seq}`
  const at = new Date().toISOString()
  audit.push({
    contract_version: '0.2', id, timestamp: at, actor,
    input: { request: { id: d.request_id, buyer_id, text, items: [], needed_by: null, created_at: at }, mandate: null, quotes: [] },
    decision: d, rejected_options: [],
  })
  return id
}

const orders = new Map<string, { buyer: string; res: OrderResponse; signedOffBy?: string }>()

const CALENDAR_TODAY = '2026-11-14'
const CALENDAR_PENDING_ID = 'mock-calendar-pending'
const calendarRecurringPlaced = new Set<string>(['2026-11-06', '2026-11-13'])
const calendarRecurringSkipped = new Set<string>()

const CALENDAR_MENU: WeeklyMenu = {
  weekday: 'fri',
  name: 'Example: Lapland special — salmon soup and blueberry pie',
  covers: 80,
  active: true,
  dishes: [
    {
      name: 'Creamy salmon soup',
      recipe: 'Sweat onion and leek in butter. Add potatoes and fish stock, then simmer until tender. Add salmon and cream; cook gently until just done. Season with dill, salt and lemon.',
    },
    {
      name: 'Blueberry quark pie',
      recipe: 'Press the butter crust into a tin. Whisk quark, sugar and eggs until smooth, fold in blueberries, and bake until the centre is set. Cool before slicing.',
    },
  ],
}
let mockWeeklyMenus: WeeklyMenu[] = [structuredClone(CALENDAR_MENU)]

const calendarLine = (name: string, quantity: number, unit: string): CalendarLine => ({ name, quantity, unit })

function ensureCalendarPendingOrder() {
  if (orders.has(CALENDAR_PENDING_ID)) return
  const d = structuredClone(MILK.decision)
  orders.set(CALENDAR_PENDING_ID, {
    buyer: 'lapland-kitchen',
    res: {
      order_id: CALENDAR_PENDING_ID,
      status: 'pending_approval',
      audit_id: 'aud-calendar-pending',
      total_cents: 156000,
      lines: [{ product_id: '463335', name: 'Valio Eila 3 % milk drink 1 L lactose free', quantity: 1000, unit: 'ST', unit_price_cents: 156, line_total_cents: 156000 }],
      decision: d,
      rejected_options: [],
      substitutes: [],
      alternative_order: null,
    },
  })
}

function calendarDays(from: string, to: string): CalendarDay[] {
  ensureCalendarPendingOrder()
  const fridayMenu = mockWeeklyMenus.find((menu) => menu.weekday === 'fri' && menu.active)
  const start = new Date(`${from}T12:00:00Z`)
  const end = new Date(`${to}T12:00:00Z`)
  const days: CalendarDay[] = []
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const date = cursor.toISOString().slice(0, 10)
    const entries: CalendarEntry[] = []
    if (date === '2026-11-02') entries.push({ kind: 'delivery_confirmed', order_id: 'mock-calendar-1102', title: 'Monday pantry restock', lines: [calendarLine('Unsalted butter', 20, 'ST')], total_cents: 9700, status: 'confirmed' })
    if (date === '2026-11-06') entries.push({ kind: 'delivery_confirmed', order_id: 'mock-calendar-1106', title: 'Friday service delivery', lines: [calendarLine('Whipping cream', 7, 'ST'), calendarLine('Milk', 12, 'ST')], total_cents: 5220, status: 'confirmed' })
    if (date === '2026-11-09') entries.push({ kind: 'delivery_confirmed', order_id: 'mock-calendar-1109', title: 'Monday dairy delivery', lines: [calendarLine('Soft quark', 2, 'KI'), calendarLine('Unsalted butter', 4, 'ST')], total_cents: 3900, status: 'confirmed' })
    if (date === '2026-11-13') entries.push({ kind: 'delivery_confirmed', order_id: 'mock-calendar-1113', title: 'Friday service delivery', lines: [calendarLine('Salmon', 12, 'kg')], total_cents: 18600, status: 'confirmed' })
    if (date === '2026-11-16') {
      const pending = orders.get(CALENDAR_PENDING_ID)?.res
      const confirmed = pending?.status === 'confirmed'
      entries.push(confirmed
        ? { kind: 'delivery_confirmed', order_id: CALENDAR_PENDING_ID, title: 'Lactose-free milk delivery', lines: [calendarLine('Lactose-free milk', 1000, 'L')], total_cents: 156000, status: 'confirmed' }
        : { kind: 'delivery_pending', order_id: CALENDAR_PENDING_ID, title: 'Lactose-free milk delivery', lines: [calendarLine('Lactose-free milk', 1000, 'L')], total_cents: 156000, status: 'pending_approval', reason: 'Waiting for your OK before the order is sent.' })
    }
    if (date === '2026-11-23') entries.push({ kind: 'delivery_confirmed', order_id: 'mock-calendar-1123', title: 'Monday pantry restock', lines: [calendarLine('Unsalted butter', 20, 'ST'), calendarLine('Milk', 12, 'ST')], total_cents: 28300, status: 'confirmed' })
    if (date === '2026-11-30') entries.push({ kind: 'delivery_confirmed', order_id: 'mock-calendar-1130', title: 'Monday pantry restock', lines: [calendarLine('Whipping cream', 8, 'ST')], total_cents: 34800, status: 'confirmed' })
    if (date === '2026-11-16' || date === '2026-11-17' || date === '2026-11-18') entries.push({ kind: 'guests_expected', value: 84, simulated: true })
    if (date === CALENDAR_TODAY) entries.push({ kind: 'guests_expected', value: 84, simulated: true })
    if (cursor.getUTCDay() === 5) {
      if (!calendarRecurringSkipped.has(date)) entries.push({ kind: 'recurring_order', weekday: 'fri', lines: [calendarLine('Döner kebab meat', 20, 'kg'), calendarLine('Unsalted butter', 10, 'kg')], source: 'Friday rotisserie standing order', placed: calendarRecurringPlaced.has(date) })
      if (fridayMenu) entries.push({ kind: 'weekly_menu', name: fridayMenu.name, dishes: fridayMenu.dishes.map((dish) => ({ name: dish.name, has_recipe: Boolean(dish.recipe?.trim()) })), covers: fridayMenu.covers })
    }
    const cutoff = date === '2026-11-16' ? { closing_time: '2026-11-15T13:00:00+02:00', passed: false } : undefined
    days.push({ date, today: date === CALENDAR_TODAY, ...(cutoff ? { cutoff } : {}), entries })
  }
  return days
}

let mockProfile: BuyerProfile = {
  buyer_id: 'lapland-kitchen',
  dietary: [{ tag: 'gluten_free', label: 'Gluten-free kitchen', because: 'You told me during onboarding.' }],
  usual_product_ids: ['463335', '464411', '463196'],
  memories: [
    {
      id: 'memory-business', kind: 'business_type', key: 'business_type', text: '60-seat bistro', scope: 'always',
      source: 'onboarding', created_at: '2026-10-12T09:00:00+03:00', used_because: 'Helps estimate menu quantities.', product_id: null,
    },
    {
      id: 'memory-milk', kind: 'usual_product', key: '463335', text: 'Valio Eila milk drink 1 l lactose free', scope: 'always',
      source: 'chosen_alternative', created_at: '2026-10-29T14:30:00+02:00', used_because: 'You chose this product for a previous order.', product_id: '463335',
    },
    {
      id: 'memory-cream', kind: 'usual_product', key: '464194', text: 'Valio whipping cream 1 l lactose free', scope: 'this_order',
      source: 'answered_question', created_at: '2026-11-07T11:15:00+02:00', used_because: 'You confirmed this product for this order.', product_id: '464194',
    },
  ],
}

export async function interviewNext(answers: InterviewAnswer[]): Promise<InterviewNextResponse> {
  await wait()
  const answered = new Set(answers.map((answer) => answer.topic))
  const next = INTERVIEW_QUESTIONS.find((question) => !answered.has(question.topic))
  return next ? { done: false, topic: next.topic, question: next.question } : { done: true, preview: structuredClone(MOCK_INTERVIEW_PREVIEW) }
}

export async function confirmInterview(answers: Record<string, unknown>): Promise<Saved> {
  await wait()
  const business = typeof answers.business_type === 'string' ? answers.business_type : null
  const dietary = Array.isArray(answers.dietary) ? answers.dietary.filter((value): value is string => typeof value === 'string') : []
  const nextMemories = [...mockProfile.memories]
  if (business) {
    nextMemories.unshift({
      id: 'memory-interview-business', kind: 'business_type', key: 'business_type', text: business, scope: 'always',
      source: 'onboarding', created_at: new Date().toISOString(), used_because: null, product_id: null,
    })
  }
  mockProfile = {
    ...mockProfile,
    dietary: dietary.length ? dietary.map((tag) => ({ tag, label: tag.replace(/_/g, '-'), because: 'You told me in the kitchen interview.' })) : mockProfile.dietary,
    memories: nextMemories,
  }
  return { stored: true, saved: Object.keys(answers), hints: [], onboarding: { onboarded: true, questions: [] } }
}

const MOCK_KITCHEN_CONTEXT: KitchenContext = {
  buyer_id: 'lapland-kitchen',
  period: { from: '2026-09-20', to: '2026-11-13' },
  covers: {
    avg_per_weekday: { mon: 46.5, tue: 52.1, wed: 48.7, thu: 61.2, fri: 78.4, sat: 84.6, sun: null },
    busiest_days: ['fri', 'sat'], last_7_days: 326, trend_pct: 8.4,
  },
  revenue: { last_7_days_eur: 18420.5, source: 'demo seed (simulated door counter and POS export)' },
  leftovers_recent: [
    { date: '2026-11-13', item: 'mashed potatoes', amount: 6.5, unit: 'kg' },
    { date: '2026-11-12', item: 'lingonberries', amount: null, unit: 'kg' },
  ],
  spend: {
    per_week_cents: [
      { week: '2026-W40', cents: 112430 }, { week: '2026-W41', cents: 128900 }, { week: '2026-W42', cents: 119750 },
      { week: '2026-W43', cents: 136420 }, { week: '2026-W44', cents: 142180 }, { week: '2026-W45', cents: 151600 },
    ],
    source: 'front door orders',
  },
  usual_products: [
    { product_id: '463335', name: 'Valio Eila milk drink 1 l lactose free', typical_quantity: 12, unit: 'ST', times_ordered: 8 },
    { product_id: '464411', name: 'Valio butter 500 g unsalted', typical_quantity: 20, unit: 'ST', times_ordered: 6 },
    { product_id: '463196', name: 'Valio soft quark 250 g', typical_quantity: 2, unit: 'KI', times_ordered: 5 },
  ],
  sources: ['demo seed (simulated door counter and POS export)', 'front door orders'],
  simulated: true,
}

const MOCK_KITCHEN_HISTORY: KitchenHistory = {
  basis: 'example',
  covers_by_weekday: { mon: 46, tue: 52, wed: 49, thu: 61, fri: 78, sat: 85, sun: null },
  covers_source: { mon: 'example', tue: 'example', wed: 'example', thu: 'example', fri: 'example', sat: 'example', sun: 'example' },
  standing_orders: [
    {
      weekday: 'fri',
      lines: [
        { text: '12 L lactose-free milk', quantity: 12, unit: 'L' },
        { text: '20 packs unsalted butter', quantity: 20, unit: 'ST' },
      ],
      source: 'example',
    },
  ],
  usual_products: [
    { product_id: '463335', name: 'Valio Eila milk drink 1 l lactose free', source: 'example' },
    { product_id: '464411', name: 'Valio butter 500 g unsalted', source: 'example' },
  ],
  labels: { example: 'Example history (simulated)' },
}

const mockKitchenHistory = structuredClone(MOCK_KITCHEN_HISTORY)

function historyBasis(history: KitchenHistory): KitchenHistory['basis'] {
  const hasExample = Object.values(history.covers_source).some((source) => source === 'example') ||
    history.standing_orders.some((order) => order.source === 'example') ||
    history.usual_products.some((product) => product.source === 'example')
  const hasOwn = Object.values(history.covers_source).some((source) => source === 'own') ||
    history.standing_orders.some((order) => order.source === 'own') ||
    history.usual_products.some((product) => product.source === 'own')
  return hasExample && hasOwn ? 'mixed' : hasExample ? 'example' : 'own'
}

function mockStandingOrders(): StandingOrder[] {
  return mockKitchenHistory.standing_orders.map((order) => structuredClone(order))
}

const MOCK_INTERVIEW_PREVIEW: InterviewPreview = {
  stored: false,
  proposed: [
    { id: 'business_type', question: 'What kind of business do you run?', value: '60-seat bistro' },
    { id: 'delivery_days', question: 'Which weekdays can you receive deliveries?', value: ['monday', 'friday'] },
    { id: 'standing_orders', question: 'What do you order regularly, and on which days?', value: [{ weekday: 'fri', lines: [{ text: '12 L lactose-free milk', quantity: 12, unit: 'L' }] }] },
    { id: 'dietary', question: 'Which diets does your whole kitchen always follow?', value: ['gluten_free'] },
    { id: 'usual_products', question: 'Which products or brands do you reach for often?', value: ['Valio Eila milk drink', 'Valio butter'] },
    { id: 'budget', question: 'What order total are you comfortable with on your own?', value: 1500 },
  ],
  unclear: [],
  hints: [],
}

const EDIT_DAYS: Weekday[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
const INTERVIEW_QUESTIONS: { topic: InterviewAnswer['topic']; question: string }[] = [
  { topic: 'kitchen', question: 'What kind of kitchen is this, and how many seats or typical guests do you serve?' },
  { topic: 'delivery_days', question: 'Which weekdays can you receive deliveries?' },
  { topic: 'standing_orders', question: 'What do you order regularly, and on which days?' },
  { topic: 'dietary_allergens', question: 'Which diets or allergens must your kitchen always avoid?' },
  { topic: 'usual_products', question: 'Which products or brands do you reach for often?' },
  { topic: 'budget', question: 'What order total are you comfortable with on your own?' },
  { topic: 'anything_else', question: 'Is there anything else I should remember about your kitchen?' },
]

// Menu → cart (POST /api/agent/menu): two dishes for 80 covers. Amounts per cover are the agent's estimates.
const menuLine = (
  item: number, dishes: string[], p: Product, price: number, amount: number, unit: string, units: number, per: number, chosen = true,
): Line => ({
  product: p,
  quote: quote({ product_id: p.id, price, sales_unit: p.sales_unit, available_amount: 9999999999, order_cutoff: '2026-11-15T13:00:00+02:00' }),
  quantity: qty(p.id, amount, unit, p.sales_unit ?? 'ST', units, per, `${amount} ${unit} ÷ ${per} ${unit} per ${p.sales_unit} = ${units} ${p.sales_unit}.`),
  line_total_cents: Math.round(price * 100 * units),
  why: chosen ? 'Best match for this ingredient, in stock for Monday.' : 'Also matches, but costs more.',
  chosen,
  confidence: chosen ? 0.93 : 0.88,
  confidence_reason: null,
  facts: { delivery_reliability: p.delivery_reliability, carbon_kg_per_kg: p.carbon_kg_per_kg, origin: 'fi' },
  item,
  dishes,
})
const SOUP = 'Creamy salmon soup'
const PIE = 'Lingonberry quark pie'
const MENU: Omit<MenuRun, 'audit_id'> = {
  menu: {
    dishes: [
      {
        name: SOUP,
        ingredients: [
          { name: 'whipping cream', per_cover: 0.05, unit: 'L', assumption: 'About 0.5 dl of cream per bowl.' },
          { name: 'milk', per_cover: 0.15, unit: 'L', assumption: 'A 2.5 dl bowl, a bit over half of it milk.' },
        ],
      },
      {
        name: PIE,
        ingredients: [
          { name: 'soft quark', per_cover: 0.06, unit: 'kg', assumption: 'One slice from a 12-slice pie.' },
          { name: 'whipping cream', per_cover: 0.03, unit: 'L', assumption: 'Cream in the filling.' },
          { name: 'butter', per_cover: 0.02, unit: 'kg', assumption: 'Butter in the crust.' },
        ],
      },
    ],
  },
  assumptions: [
    { ingredient: 'whipping cream', dish: SOUP, per_cover: 0.05, unit: 'L', text: 'About 0.5 dl of cream per bowl.' },
    { ingredient: 'milk', dish: SOUP, per_cover: 0.15, unit: 'L', text: 'A 2.5 dl bowl, a bit over half of it milk.' },
    { ingredient: 'soft quark', dish: PIE, per_cover: 0.06, unit: 'kg', text: 'One slice from a 12-slice pie.' },
    { ingredient: 'whipping cream', dish: PIE, per_cover: 0.03, unit: 'L', text: 'Cream in the filling.' },
    { ingredient: 'butter', dish: PIE, per_cover: 0.02, unit: 'kg', text: 'Butter in the crust.' },
  ],
  ingredients: [
    { query: 'whipping cream', amount: 6.4, unit: 'L', claims: [], exclude_allergens: [], dishes: [SOUP, PIE] },
    { query: 'milk', amount: 12, unit: 'L', claims: [], exclude_allergens: [], dishes: [SOUP] },
    { query: 'soft quark', amount: 4.8, unit: 'kg', claims: [], exclude_allergens: [], dishes: [PIE] },
    { query: 'butter', amount: 1.6, unit: 'kg', claims: [], exclude_allergens: [], dishes: [PIE] },
  ],
  lines: [
    menuLine(0, [SOUP, PIE], product({ id: '464194', name_en: 'Valio whipping cream 1 l UHT lactose free', sales_unit: 'ST', delivery_reliability: 1 }), 4.35, 6.4, 'L', 7, 1),
    menuLine(0, [SOUP, PIE], product({ id: '464699', name_en: 'Valio whipping cream 1 l lactose free, organic', sales_unit: 'ST', delivery_reliability: 0.947 }), 5.9, 6.4, 'L', 7, 1, false),
    menuLine(1, [SOUP], product({ id: '463335', name_en: 'Valio Eila® 3 % milk drink 1 l lactose free', sales_unit: 'ST', delivery_reliability: 1 }), 1.56, 12, 'L', 12, 1),
    menuLine(2, [PIE], product({ id: '463196', name_en: 'Valio soft quark 250 g', sales_unit: 'KI', claims: [], delivery_reliability: 0.98 }), 9.8, 4.8, 'kg', 2, 3),
    menuLine(3, [PIE], product({ id: '464411', name_en: 'Valio butter 500 g unsalted', sales_unit: 'ST', claims: [], delivery_reliability: 1 }), 4.85, 1.6, 'kg', 4, 0.5),
  ],
  cart_total_cents: 3045 + 1872 + 1960 + 1940,
  order_lines: [
    { product_id: '464194', quantity: 7 },
    { product_id: '463335', quantity: 12 },
    { product_id: '463196', quantity: 2 },
    { product_id: '464411', quantity: 4 },
  ],
  decision: decision(
    'ASK_HUMAN',
    [
      reason('MENU_ASSUMPTIONS', 'ASK_HUMAN', 'This cart is a proposal for 80 covers: the quantities rest on per-cover assumptions (listed with the cart). Nothing is ordered until you confirm.', {
        suggested_fix: 'Check the amounts per cover, then order the cart.',
      }),
    ],
    [],
    0.93,
  ),
}

// --- Rules: the seeded Lapland kitchen mandate, a tiny rule reader, and the backend's diff wording.
let mandateVersion = 1
let mandate: Mandate = {
  contract_version: '0.2', id: 'lapland-kitchen-2026-11', buyer_id: 'lapland-kitchen', uncertainty_policy: 'ask',
  hard_rules: [
    { kind: 'excluded_allergen', value: 'AP', scope: 'always', source_text: 'Our kitchen is peanut-free.' },
    { kind: 'auto_approve_limit_cents', value: 150000, scope: 'always', source_text: 'Order on your own up to 1,500 euros per order; above that, ask me.' },
    { kind: 'min_delivery_reliability', value: 0.9, scope: 'always', source_text: 'Deliveries up here are fragile: ask me before anything that arrives on time under 90%.' },
  ],
  guidance: [{ text: 'Prefer Finnish-origin products when the price is similar.', scope: 'always' }],
  open_questions: [], blocklist: [], per_line_cap_cents: 200000, weekly_budget_cents: 600000, expires_at: null,
}
const ALLERGEN_WORDS: [RegExp, string, string][] = [
  [/peanut/i, 'AP', 'peanuts'], [/gluten/i, 'AW', 'gluten (cereals)'], [/\bmilk|dairy/i, 'AM', 'milk'], [/\begg/i, 'AE', 'egg'],
  [/\bfish/i, 'AF', 'fish'], [/tree nut|\bnuts?\b/i, 'AN', 'tree nuts'], [/\bsoy/i, 'AY', 'soy'], [/sesame/i, 'AS', 'sesame'],
]
const eurText = (c: number | null) => (c == null ? 'none' : `EUR ${(c / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}`)
const money = (s: string) => Math.round(Number(s.replace(/[,\s]/g, '')) * 100)

function readRules(text: string): Mandate {
  const sentences = text.split(/(?<=[.!?])\s+|\n+/).map((x) => x.trim()).filter(Boolean)
  const said = (re: RegExp) => sentences.find((x) => re.test(x)) ?? null
  const rules: Mandate['hard_rules'] = []
  for (const [re, code] of ALLERGEN_WORDS) {
    const s = said(re)
    if (s && !/prefer/i.test(s)) rules.push({ kind: 'excluded_allergen', value: code, scope: 'always', source_text: s })
  }
  const auto = said(/(up to|on (its|your) own)[^.]*?(€\s?)?\d[\d,]*/i)
  const autoV = auto && /(?:€\s?)?(\d[\d,]*)\s*(?:€|euros?)?/i.exec(auto.replace(/^[^\d€]*/, ''))
  rules.push({ kind: 'auto_approve_limit_cents', value: autoV ? money(autoV[1]) : 50000, scope: 'always', source_text: auto ?? 'Default: no auto-approve limit was stated.' })
  const rel = said(/on time[^.]*?\d+\s*%/i)
  if (rel) rules.push({ kind: 'min_delivery_reliability', value: Number(/(\d+)\s*%/.exec(rel)![1]) / 100, scope: 'always', source_text: rel })
  const line = said(/one product|per line/i)
  const week = said(/a week|per week|weekly/i)
  const local = said(/local/i)
  return {
    ...mandate, id: 'lapland-kitchen-draft', hard_rules: rules,
    guidance: sentences.filter((x) => /^prefer/i.test(x)).map((t) => ({ text: t, scope: 'always' })),
    per_line_cap_cents: line ? money(/(\d[\d,]*)/.exec(line)![1]) : 30000,
    weekly_budget_cents: week ? money(/(\d[\d,]*)/.exec(week)![1]) : null,
    open_questions: local && !/finnish|finland/i.test(local)
      ? [{ question: `I noted “${local}” as a wish, but I can’t check “local” automatically yet. Should I ask you about it on each order?`, why: 'No automatic check exists yet for this kind of rule.' }]
      : [],
  }
}

function diffRules(a: Mandate, b: Mandate): RuleChange[] {
  const out: RuleChange[] = []
  const add = (field: string, before: unknown, after: unknown, change: RuleChange['change'], text: string, large = false) =>
    out.push({ field, before, after, change, text, needs_confirmation: large })
  const num = (m: Mandate, kind: string) => {
    const v = m.hard_rules.filter((r) => r.kind === kind).map((r) => Number(r.value))
    return v.length ? Math.min(...v) : null
  }
  const limits: [string, string, (m: Mandate) => number | null][] = [
    ['auto_approve_limit_cents', 'auto-approve limit per order', (m) => num(m, 'auto_approve_limit_cents')],
    ['per_line_cap_cents', 'per-line cap', (m) => m.per_line_cap_cents],
    ['weekly_budget_cents', 'weekly budget', (m) => m.weekly_budget_cents],
  ]
  for (const [field, label, get] of limits) {
    const x = get(a), y = get(b)
    if (x !== y) {
      const looser = y === null || (x !== null && y > x)
      add(field, x, y, looser ? 'looser' : 'tighter', `${label}: ${eurText(x)} → ${eurText(y)}${y === null ? ' (no limit at all)' : ''}`,
        looser && (y === null || (x !== null && y / x > 10)))
    }
  }
  const set = (m: Mandate) => new Set(m.hard_rules.filter((r) => r.kind === 'excluded_allergen').map((r) => String(r.value)))
  const name = (c: string) => ALLERGEN_WORDS.find(([, code]) => code === c)?.[2] ?? c
  const [xa, ya] = [set(a), set(b)]
  for (const v of ya) if (!xa.has(v)) add('excluded_allergens', null, v, 'tighter', `new excluded allergen: ${name(v)}`)
  for (const v of xa) if (!ya.has(v)) add('excluded_allergens', v, null, 'looser', `excluded allergen removed: ${name(v)}`, true)
  const xr = a.hard_rules.find((r) => r.kind === 'min_delivery_reliability')?.value ?? null
  const yr = b.hard_rules.find((r) => r.kind === 'min_delivery_reliability')?.value ?? null
  if (xr !== yr) {
    const pct = (v: unknown) => (v === null ? 'none' : `${Math.round(Number(v) * 100)}%`)
    const looser = yr === null || (xr !== null && Number(yr) < Number(xr))
    add('min_delivery_reliability', xr, yr, looser ? 'looser' : 'tighter', `on-time delivery floor: ${pct(xr)} → ${pct(yr)}`, looser && yr === null)
  }
  const g = (m: Mandate) => m.guidance.map((x) => x.text).sort()
  if (JSON.stringify(g(a)) !== JSON.stringify(g(b))) add('guidance', g(a), g(b), 'changed', 'guidance changed (soft or administrative)')
  return out
}

let voiceTurn = 0
const WEEKDAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
// The date the backend would read from the words ("Friday", "tomorrow"), else the override, else next Monday.
function dateFrom(text: string, override?: string): string {
  if (override) return override
  const today = new Date(`${new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date())}T00:00:00Z`)
  const plus = (n: number) => new Date(today.getTime() + n * 86_400_000).toISOString().slice(0, 10)
  if (/tomorrow/i.test(text)) return plus(1)
  const day = WEEKDAYS.findIndex((d) => new RegExp(`\\b${d}\\b`, 'i').test(text))
  const target = day >= 0 ? day : 1
  return plus(((target - today.getUTCDay() + 7) % 7) || 7)
}

export const mockApi = {
  async profile(): Promise<BuyerProfile> {
    await wait()
    return structuredClone(mockProfile)
  },

  async forgetMemory(id: string): Promise<BuyerProfile> {
    await wait()
    mockProfile = { ...mockProfile, memories: mockProfile.memories.filter((memory) => memory.id !== id) }
    return structuredClone(mockProfile)
  },

  async kitchenContext(): Promise<KitchenContext> {
    await wait()
    return structuredClone(MOCK_KITCHEN_CONTEXT)
  },

  async kitchenHistory(): Promise<KitchenHistory> {
    await wait()
    return structuredClone(mockKitchenHistory)
  },

  async saveKitchenCovers(covers: Record<Weekday, number>): Promise<void> {
    await wait()
    for (const day of EDIT_DAYS) {
      if (typeof covers[day] !== 'number' || !Number.isInteger(covers[day]) || covers[day] < 0) continue
      mockKitchenHistory.covers_by_weekday[day] = covers[day]
      mockKitchenHistory.covers_source[day] = 'own'
    }
    mockKitchenHistory.basis = historyBasis(mockKitchenHistory)
  },

  async clearExampleHistory(): Promise<void> {
    await wait()
    for (const day of EDIT_DAYS) {
      if (mockKitchenHistory.covers_source[day] === 'example') {
        mockKitchenHistory.covers_by_weekday[day] = null
        mockKitchenHistory.covers_source[day] = 'own'
      }
    }
    mockKitchenHistory.standing_orders = mockKitchenHistory.standing_orders.filter((order) => order.source !== 'example')
    mockKitchenHistory.usual_products = mockKitchenHistory.usual_products.filter((product) => product.source !== 'example')
    mockKitchenHistory.basis = 'own'
  },

  async saveStandingOrder(weekday: Weekday, lines: StandingOrderLine[]): Promise<StandingOrderUpdate> {
    await wait()
    mockKitchenHistory.standing_orders = mockKitchenHistory.standing_orders.filter((order) => order.weekday !== weekday)
    if (lines.length) mockKitchenHistory.standing_orders.push({ weekday, lines: structuredClone(lines), source: 'own' })
    mockKitchenHistory.basis = historyBasis(mockKitchenHistory)
    return { standing_orders: mockStandingOrders() }
  },

  async deleteStandingOrder(weekday: Weekday): Promise<StandingOrderUpdate> {
    await wait()
    mockKitchenHistory.standing_orders = mockKitchenHistory.standing_orders.filter((order) => order.weekday !== weekday)
    mockKitchenHistory.basis = historyBasis(mockKitchenHistory)
    return { standing_orders: mockStandingOrders() }
  },

  async calendar(from: string, to: string): Promise<CalendarResponse> {
    await wait()
    return {
      days: calendarDays(from, to),
      legend: { delivery: 'delivery', pending: 'waiting for your OK', recurring: 'recurring order', menu: 'weekly menu', guests: 'guests expected' },
    }
  },

  async weeklyMenus(): Promise<WeeklyMenu[]> {
    await wait()
    return structuredClone(mockWeeklyMenus)
  },

  async saveWeeklyMenu(weekday: Weekday, menu: WeeklyMenu): Promise<WeeklyMenu> {
    await wait()
    const next = { ...structuredClone(menu), weekday, active: true }
    mockWeeklyMenus = [...mockWeeklyMenus.filter((item) => item.weekday !== weekday), next]
    return structuredClone(next)
  },

  async deleteWeeklyMenu(weekday: Weekday): Promise<void> {
    await wait()
    mockWeeklyMenus = mockWeeklyMenus.filter((item) => item.weekday !== weekday)
  },

  async planWeeklyMenu(weekday: Weekday, date: string): Promise<MenuRun> {
    await wait()
    const menu = mockWeeklyMenus.find((item) => item.weekday === weekday) ?? CALENDAR_MENU
    return mockApi.menu({ menu_text: menu.name, covers: menu.covers ?? 80, requested_date: date })
  },

  async placeRecurring(weekday: Weekday, date: string): Promise<AskResponse> {
    await wait()
    if (weekday !== 'fri') throw new Error('This mock only has a Friday standing order.')
    calendarRecurringPlaced.add(date)
    calendarRecurringSkipped.delete(date)
    return mockApi.ask({ text: '20 kg döner kebab meat for Friday', requested_date: date })
  },

  async skipRecurring(_weekday: Weekday, date: string): Promise<{ skipped: boolean }> {
    await wait()
    calendarRecurringSkipped.add(date)
    calendarRecurringPlaced.delete(date)
    return { skipped: true }
  },

  // Pretend speech-to-text: the demo's example sentences, in turn.
  async transcribe(audio: Blob): Promise<string> {
    await wait()
    if (audio.size === 0) throw new Error('Nothing was recorded. Hold the mic while you talk, or type it.')
    return ['1000 L lactose-free milk for Monday', '20 kg döner kebab meat for the rotisserie, Friday'][voiceTurn++ % 2]
  },

  // The streamed version: the backend's phases, a beat apart, then the same answer as ask().
  async askStream(input: AskInput, onPhase: (p: { phase: string; text: string }) => void): Promise<AskResponse> {
    const menu = /\bmenu\b|guests|covers|portions|people/i.test(input.text)
    const steps = [
      ['understanding', 'Reading your request…'],
      ...(menu ? [['planning', 'Turning the menu into ingredients…']] : []),
      ['searching', 'Searching Valio’s catalogue…'],
      ['stock', 'Checking Valio stock and prices…'],
      ['judging', 'Asking Gemini to double-check each match…'],
      ...(menu ? [] : [['ordering', 'Placing the order at Valio’s front door…']]),
    ]
    for (const [phase, text] of steps) {
      onPhase({ phase, text })
      await new Promise((r) => setTimeout(r, 450))
    }
    return mockApi.ask(input)
  },

  async ask(input: AskInput): Promise<AskResponse> {
    const text = input.text.trim()
    const requested_date = dateFrom(text, input.requested_date)
    if (text.length < 8 || /^(hi|hello|help|test)\b/i.test(text)) {
      await wait()
      return { intent: 'unclear', requested_date, question: 'What should the agent order? Say what, how much and when, like “20 kg döner kebab meat for Friday”.' }
    }
    if (/\bmenu\b|guests|covers|portions|people/i.test(text)) {
      const n = /(\d+)\s*(guests|covers|people|portions)/i.exec(text)
      if (!n) {
        await wait()
        return { intent: 'menu', requested_date, question: 'For how many guests?' }
      }
      const covers = Number(n[1])
      return { intent: 'menu', requested_date, covers, ...(await mockApi.menu({ menu_text: text, covers, requested_date })) }
    }
    if (/d[öo]ner|kebab/i.test(text)) {
      await wait()
      const f = structuredClone(DONER)
      const audit_id = log('buyer_agent', 'lapland-kitchen', text, f.decision)
      const order: OrderResponse = {
        order_id: `00000000-0000-4000-8000-${String(seq + 1).padStart(12, '0')}`, status: 'confirmed',
        audit_id: log('valio_front_door', 'lapland-kitchen', `Order via Valio front door: ${f.request.summary}`, f.decision),
        total_cents: 12980, lines: [{ product_id: '480001', name: f.lines[0].product.name_en!, quantity: 2, unit: 'ST', unit_price_cents: 6490, line_total_cents: 12980 }],
        decision: f.decision, rejected_options: [], substitutes: [], alternative_order: null,
      }
      return { intent: 'order', requested_date, request: f.request, lines: f.lines, decision: f.decision, order, audit_id }
    }
    // The demo only has canned answers for the requests listed at the top of this file. Anything else used to fall
    // through to a confirmed butter order, which looked like a real (and wrong) result. Say so instead.
    if (!/stock|split|butter|drink|1[ ,]?000|cream|tomorrow|error/i.test(text)) {
      await wait()
      return {
        intent: 'unclear', requested_date,
        question: 'This is demo data with canned answers for only a few requests, so it can’t answer this one. Try “1000 L lactose-free milk for Monday”, “20 kg döner kebab meat for Friday” or “Menu for 80 guests”. For real answers, run the backend and open the app without ?mock=1.',
      }
    }
    const res = { intent: 'order' as const, requested_date, ...(await mockApi.run({ text, requested_date })) }
    // Helsinki bistro, in a hurry: the same suggestions the backend makes (urgent.py), never an order.
    if (/\b(asap|now|today|urgent|heti|nyt|tänään|kiire)/i.test(text)) {
      const ready = new Date(Date.now() + 4 * 3_600_000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Helsinki' })
      return { ...res, urgent_options: [
        { kind: 'walk_in', label: 'Pick it up yourself now: Valio Aimo Cash & Carry Helsinki', address: 'Vanha Talvitie 2, Helsinki (Sörnäinen, Tukkutori)',
          hours: 'today 08:00–17:00 (open now)', phone: '010 381 7645', assumption: true,
          text: 'Vanha Talvitie 2, Helsinki (Sörnäinen, Tukkutori), today 08:00–17:00 (open now). Store stock is not confirmed via the API: call 010 381 7645 before you go.' },
        { kind: 'click_and_collect', label: 'Click & Collect (Helsinki only)', assumption: true,
          text: `Order for pickup at Valio Aimo Cash & Carry Helsinki: ready from about 4 hours after it is confirmed (around ${ready} if confirmed now, within opening hours). Placed on Valio's own site; the agent doesn't place pickup orders.` },
        { kind: 'next_delivery', label: 'Next delivery', assumption: false, text: `The earliest Valio delivery for these products is ${requested_date} if ordered before 2026-11-15T13:00:00+02:00.` },
      ] }
    }
    return res
  },


  async getMandate(): Promise<{ mandate: Mandate; etag: string }> {
    await wait()
    return { mandate: structuredClone(mandate), etag: `"v${mandateVersion}"` }
  },

  async compile(text: string): Promise<CompileResult> {
    await wait()
    const proposed = readRules(text)
    return {
      proposed_mandate: proposed, diff_from_current: diffRules(mandate, proposed), open_questions: proposed.open_questions,
      assumptions: [
        'Money amounts are read as net of VAT (Valio’s customer price without VAT).',
        'Rules apply to every order unless you said ‘this order’.',
        'Anything you didn’t mention goes back to the safe default; see the changes list.',
      ],
      used_fallback: false, injection_flagged: /ignore (all|previous)/i.test(text),
    }
  },

  async saveMandate(next: Mandate, etag: string | null): Promise<SaveResult & { etag: string }> {
    await wait()
    if (etag && etag !== `"v${mandateVersion}"`)
      throw new ApiError(412, 'The rules changed since you loaded them; reload, review and save again.')
    mandateVersion++
    if (next.open_questions.length) throw new Error('Request failed (422): Answer the open questions first (or remove them), then save.')
    const changes = diffRules(mandate, next)
    mandate = { ...structuredClone(next), id: `lapland-kitchen-${Date.now()}` }
    const d = decision('AUTO', changes.map((c) => reason('LIMIT_CHANGE_ATTEMPT', 'INFO', `Chef (mock key) changed the rules: ${c.text} (${c.change}).`)))
    return { etag: `"v${mandateVersion}"`, mandate: structuredClone(mandate), changes, audit_id: log('human:Chef (mock key):mandate', 'lapland-kitchen', `Rules changed by Chef (mock key): ${changes.map((c) => c.text).join('; ') || 'no changes'}`, d) }
  },


  async menu(input: MenuInput): Promise<MenuRun> {
    await wait()
    if (input.menu_text.toLowerCase().includes('error')) throw new Error('Request failed (500): mock backend error')
    const m = structuredClone(MENU)
    m.decision.reasons[0].message = m.decision.reasons[0].message.replace('80 covers', `${input.covers} covers`)
    return { ...m, audit_id: log('buyer_agent', 'lapland-kitchen', `Menu for ${input.covers} covers: ${input.menu_text}`, m.decision) }
  },

  async health(): Promise<Health> {
    await wait()
    return { status: 'ok', valio_key_configured: true, gemini_key_configured: true, catalogue: { ready: true, products: 17546, error: null } }
  },

  async run(input: RunInput): Promise<AgentRun> {
    await wait()
    const text = input.text.toLowerCase()
    if (text.includes('error')) throw new Error('Request failed (500): mock backend error')
    const f = structuredClone(
      /stock|split/.test(text) || (/butter/.test(text) && /1[ ,]?000/.test(text)) ? SHORT : /drink/.test(text) ? DRINK : /1[ ,]?000/.test(text) ? MILK : /cream|tomorrow/.test(text) ? CREAM : BUTTER,
    )
    const buyer = input.buyer_id ?? 'lapland-kitchen' // the real backend takes it from the agent key
    const chosen = f.lines.filter((l) => l.chosen)
    const agentDecision = f.agent ?? f.decision
    const audit_id = log('buyer_agent', buyer, input.text, agentDecision) // the agent's decision is logged first
    if (f.status === null) return { request: f.request, lines: f.lines, decision: agentDecision, order: null, audit_id }
    const order: OrderResponse = {
      order_id: f.status === 'refused' ? null : `00000000-0000-4000-8000-${String(seq + 1).padStart(12, '0')}`,
      status: f.status,
      audit_id: log('valio_front_door', buyer, `Order via Valio front door: ${f.request.summary}`, f.decision),
      total_cents: chosen.reduce((a, l) => a + (l.line_total_cents ?? 0), 0),
      lines: chosen.map((l) => ({
        product_id: l.product.id, name: l.product.name_en ?? l.product.id, quantity: l.quantity?.quantity ?? null,
        unit: l.product.sales_unit, unit_price_cents: l.quote?.price != null ? Math.round(l.quote.price * 100) : null,
        line_total_cents: l.line_total_cents,
      })),
      decision: f.decision,
      rejected_options: [],
      substitutes: f.substitutes ?? [],
      alternative_order: f.alternative_order ?? null,
    }
    if (order.order_id) orders.set(order.order_id, { buyer: buyer, res: order })
    return { request: f.request, lines: f.lines, decision: agentDecision, order, audit_id }
  },

  // The front door re-checks a placed order; here anything over €1,000 needs the chef's OK.
  async place(input: OrderInput): Promise<OrderResponse> {
    await wait()
    const known = new Map<string, { name: string; unit: string | null; cents: number | null }>()
    for (const f of [MILK, BUTTER, CREAM, SHORT, { lines: MENU.lines, substitutes: [] }]) {
      for (const l of f.lines) known.set(l.product.id, { name: l.product.name_en ?? l.product.id, unit: l.product.sales_unit, cents: l.quote?.price != null ? Math.round(l.quote.price * 100) : null })
      for (const s of f.substitutes ?? []) known.set(s.product_id, { name: s.name, unit: s.unit, cents: s.unit_price_cents })
    }
    const lines = input.lines.map(({ product_id, quantity }) => {
      const k = known.get(product_id)
      return {
        product_id, name: k?.name ?? product_id, quantity, unit: k?.unit ?? null, unit_price_cents: k?.cents ?? null,
        line_total_cents: k?.cents != null ? Math.round(k.cents * quantity) : null,
      }
    })
    const total = lines.reduce((a, l) => a + (l.line_total_cents ?? 0), 0)
    const over = total > 100000
    const d = decision(over ? 'ASK_HUMAN' : 'AUTO', over ? [reason('SPEND_OVER_LIMIT', 'ASK_HUMAN', `This order is ${(total / 100).toFixed(2)} € net, above your €1,000.00 auto-order limit.`, { suggested_fix: 'Approve, or reduce the order.' })] : [])
    const res: OrderResponse = {
      order_id: `00000000-0000-4000-8000-${String(seq + 1).padStart(12, '0')}`, status: over ? 'pending_approval' : 'confirmed',
      audit_id: log('valio_front_door', 'lapland-kitchen', 'Order via Valio front door (split proposal)', d),
      total_cents: total, lines, decision: d, rejected_options: [], substitutes: [], alternative_order: null,
    }
    orders.set(res.order_id!, { buyer: 'lapland-kitchen', res })
    return res
  },

  async decide(orderId: string, action: 'approve' | 'reject'): Promise<OrderResponse> {
    await wait()
    const o = orders.get(orderId)
    if (!o) throw new Error('Request failed (404): Unknown order id')
    if (o.res.status !== 'pending_approval') throw new Error(`Request failed (409): Order is ${o.res.status}, not pending approval`)
    const status: OrderStatus = action === 'approve' ? 'confirmed' : 'rejected'
    const d = o.res.decision // the backend re-runs the gate on approve; the reasons the human saw stay on it
    o.res = { ...o.res, status, decision: d, audit_id: log(`human:Chef (mock key):${action}`, o.buyer, `Order ${orderId}`, d) }
    o.signedOffBy = 'Chef (mock key)'
    return o.res
  },

  async order(orderId: string): Promise<{ signed_off_by: string | null; status: OrderStatus }> {
    await wait()
    const o = orders.get(orderId)
    return { signed_off_by: o?.signedOffBy ?? null, status: o?.res.status ?? 'refused' }
  },

  // Talk: a scripted conversation, timed like the real one (the agent's audio is left out: captions only).
  async live(
    h: Pick<LiveSocket, 'onEvent' | 'onClose'> | { onEvent: (event: KitchenLiveEvent) => void; onClose: () => void },
    mode: 'order' | 'interview' = 'order',
  ): Promise<Pick<LiveSocket, 'send' | 'close'>> {
    let closed = false
    const timers: number[] = []
    const handler = h as { onEvent: (event: KitchenLiveEvent) => void; onClose: () => void }
    const at = (ms: number, e: KitchenLiveEvent) => timers.push(window.setTimeout(() => !closed && handler.onEvent(e), ms))
    if (mode === 'interview') {
      at(300, { type: 'ready' })
      at(1000, { type: 'transcript', role: 'agent', text: 'What kind of kitchen is this, and how many guests do you serve?', final: true })
      at(1900, { type: 'transcript', role: 'user', text: 'A 60-seat bistro in Lapland.', final: true })
      at(2700, { type: 'transcript', role: 'agent', text: 'Which weekdays can you receive deliveries?', final: true })
      at(3600, { type: 'transcript', role: 'user', text: 'Monday and Friday.', final: true })
      at(4400, { type: 'interview_preview', preview: structuredClone(MOCK_INTERVIEW_PREVIEW) })
      at(5000, { type: 'transcript', role: 'agent', text: "Here's what I'll remember. Check it on screen and confirm.", final: true })
      at(5600, { type: 'turn_complete' })
    } else {
      const run = await mockApi.ask({ text: '1000 L lactose-free milk for Monday' })
      at(300, { type: 'ready' })
      at(1500, { type: 'transcript', role: 'user', text: 'I need lactose-free milk for Monday', final: false })
      at(2300, { type: 'transcript', role: 'user', text: 'I need lactose-free milk for Monday, a thousand litres.', final: true })
      at(2700, { type: 'transcript', role: 'agent', text: 'Give me a second to check Valio.', final: true })
      at(3000, { type: 'tool', name: 'ask', status: 'running', label: 'Checking Valio prices…' })
      at(5200, { type: 'tool', name: 'ask', status: 'done', label: 'Checked Valio prices' })
      at(5300, { type: 'result', payload: run })
      at(5600, { type: 'transcript', role: 'agent', text: 'That’s 1,560 euros, 60 over your limit, so it needs your OK. Approve it on screen.', final: true })
      at(6200, { type: 'turn_complete' })
    }
    return {
      send: () => {},
      close: () => {
        closed = true
        timers.forEach(clearTimeout)
        handler.onClose()
      },
    }
  },

  async readPhoto(): Promise<PhotoRead> {
    await wait()
    return { kind: 'note', text: '20 kg butter and 30 L cream for Friday', items: ['20 kg butter', '30 L cream'], covers: null, unreadable: ['one smudged line'], language: 'en' }
  },

  async audit(): Promise<AuditEntry[]> {
    await wait()
    return audit
  },

  // Valio's view: the same trail with the front door's note (and a stand-in signature), plus two refused attempts.
  async adminAudit(f: AdminFilter): Promise<AdminRow[]> {
    await wait()
    const at = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
    const security: SecurityEvent[] = [
      { kind: 'security_event', id: 'sec-1', timestamp: at(42), event: 'cross_buyer_attempt', route: 'approve order', buyer_id: null, caller_buyer_id: 'helsinki-bistro' },
      { kind: 'security_event', id: 'sec-2', timestamp: at(15), event: 'invalid_key', route: 'POST /api/agent/ask', buyer_id: null, header: 'X-Agent-Key' },
    ]
    const rows: AdminRow[] = audit.map((e) => {
      const status = e.actor === 'valio_front_door' ? (e.decision.outcome === 'AUTO' ? 'confirmed' : e.decision.outcome === 'DECLINE' ? 'refused' : 'pending_approval') : null
      return { ...e, front_door: status ? { action: 'order', status, signed_statement: { order_id: e.input.request.id }, signature: { alg: 'EdDSA' } } : { action: 'decide' } }
    })
    return [...security, ...rows]
      .filter((r) => (r.kind ? !f.outcome && !f.status : (!f.outcome || r.decision.outcome === f.outcome) && (!f.status || r.front_door?.status === f.status)))
      .filter((r) => !f.buyer_id || (r.kind ? (r.buyer_id ?? r.caller_buyer_id) : r.input.request.buyer_id) === f.buyer_id)
      .sort((x, y) => x.timestamp.localeCompare(y.timestamp))
  },
}
