// Mock backend for VITE_MOCK=1 / ?mock=1 (dev only). Products are real catalogue entries; prices,
// stock and cut-offs are illustrative. Which fixture you get depends on the request text:
//   contains "1000" / "1 000" / "1,000"  -> ASK_HUMAN, order pending_approval (the lactose-free milk case)
//   contains "cream" or "tomorrow"       -> refused at the front door (cut-off passed)
//   contains "stock" or "split"          -> refused for partial stock, with substitutes + a split order proposal
//   contains "error"                     -> a failed request (to see the error state)
//   anything else                        -> AUTO, order confirmed (small butter order)
import type {
  AgentRun, Alternative, AlternativeOrder, AuditEntry, Decision, Health, Line, OrderInput, OrderResponse, OrderStatus,
  CompileResult, Mandate, MenuInput, MenuRun, Product, RuleChange, SaveResult, Quote, QuantityResolution, Reason, RunInput, Substitute,
} from './types'

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

export const mockApi = {
  async getMandate(): Promise<Mandate> {
    await wait()
    return structuredClone(mandate)
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

  async saveMandate(next: Mandate): Promise<SaveResult> {
    await wait()
    if (next.open_questions.length) throw new Error('Request failed (422): Answer the open questions first (or remove them), then save.')
    const changes = diffRules(mandate, next)
    mandate = { ...structuredClone(next), id: `lapland-kitchen-${Date.now()}` }
    const d = decision('AUTO', changes.map((c) => reason('LIMIT_CHANGE_ATTEMPT', 'INFO', `Chef (mock key) changed the rules: ${c.text} (${c.change}).`)))
    return { mandate: structuredClone(mandate), changes, audit_id: log('human:Chef (mock key):mandate', 'lapland-kitchen', `Rules changed by Chef (mock key): ${changes.map((c) => c.text).join('; ') || 'no changes'}`, d) }
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
      /stock|split/.test(text) ? SHORT : /drink/.test(text) ? DRINK : /1[ ,]?000/.test(text) ? MILK : /cream|tomorrow/.test(text) ? CREAM : BUTTER,
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

  async order(orderId: string): Promise<{ signed_off_by: string | null }> {
    await wait()
    return { signed_off_by: orders.get(orderId)?.signedOffBy ?? null }
  },

  async audit(): Promise<AuditEntry[]> {
    await wait()
    return audit
  },
}
