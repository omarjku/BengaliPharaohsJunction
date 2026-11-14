// Mock backend for ?mock=1 / VITE_MOCK=1. Products are real catalogue entries; prices,
// stock and cut-offs are illustrative. Which fixture you get depends on the request text:
//   contains "1000" / "1 000" / "1,000"  -> NEEDS_APPROVAL (the lactose-free milk case)
//   contains "cream" or "tomorrow"       -> REFUSED
//   contains "error"                     -> a failed request (to see the error state)
//   anything else                        -> ORDERED (small butter order)
import type { AgentRun, ApprovalResult, AuditEntry, Health, Product, Quote, RunInput } from './types'

const product = (p: Partial<Product> & Pick<Product, 'id' | 'name_en' | 'sales_unit'>): Product => ({
  name_fi: null,
  brand: 'Valio',
  claims: ['FREE_FROM_LACTOSE'],
  allergens: { contains: ['AM'], may_contain: [], free_from: [] },
  delivery_reliability: null,
  carbon_kg_per_kg: 1.1,
  ...p,
})

const quote = (q: Partial<Quote>): Quote => ({
  price: null,
  comparison_price: null,
  comparison_unit: null,
  available_amount: null,
  quantity_known: true,
  order_cutoff: null,
  available_date: '2026-11-16',
  flags: [],
  orderable: true,
  ...q,
})

const MILK: Omit<AgentRun, 'audit_id' | 'order'> = {
  request: {
    summary: '1000 L lactose-free milk, delivered Monday 16 Nov',
    items: [{ query: 'lactose-free milk', amount: 1000, unit: 'L', claims: ['FREE_FROM_LACTOSE'], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({
        id: '463335',
        name_en: 'Valio Eila® 3 % milk drink 1 l lactose free',
        name_fi: 'Valio Eila® 3 % maitojuoma 1 l laktoositon',
        sales_unit: 'ST',
        delivery_reliability: 1.0,
      }),
      quote: quote({
        price: 1.4, comparison_price: 1.4, comparison_unit: 'L', available_amount: 2400,
        order_cutoff: '2026-11-15T13:00:00+02:00',
      }),
      quantity: { sales_units: 1000, explanation: '1000 L ÷ 1 L per ST = 1000 ST', needs_confirmation: false },
      line_total_cents: 140000,
      why: 'Lactose free, 1 l cartons in stock for Monday, best delivery reliability (100 %).',
      chosen: true,
    },
    {
      product: product({ id: '463038', name_en: 'Valio Eila® semi skimmed milk drink 10 l novobox lactose free', sales_unit: 'KI' }),
      quote: quote({
        price: 13.2, comparison_price: 0.66, comparison_unit: 'L', quantity_known: false,
        order_cutoff: '2026-11-12T15:00:00+02:00', flags: ['cutoff_passed', 'quantity_unknown'], orderable: false,
      }),
      quantity: { sales_units: 50, explanation: '1000 L ÷ 20 L per KI (2 × 10 l boxes) = 50 KI', needs_confirmation: false },
      line_total_cents: 66000,
      why: 'Cheaper per litre, but the order deadline for Monday has passed.',
      chosen: false,
    },
    {
      product: product({ id: '462775', name_en: 'Arla Milkdrink 1L lactose free fat free UHT Suomesta', brand: 'Arla', sales_unit: 'ST' }),
      quote: quote({ price: 1.25, comparison_price: 1.25, comparison_unit: 'L', available_amount: 51, flags: ['partial_stock'] }),
      quantity: { sales_units: 1000, explanation: '1000 L ÷ 1 L per ST = 1000 ST', needs_confirmation: false },
      line_total_cents: 125000,
      why: 'Lactose free, but only 51 of 1000 in stock.',
      chosen: false,
    },
  ],
  decision: {
    outcome: 'NEEDS_APPROVAL',
    reasons: [
      { code: 'SPEND_LIMIT', severity: 'needs_approval', text: 'Order total €1,400.00 exceeds the €1,000.00 auto-order limit for this buyer.' },
    ],
    alternatives: [
      { product_id: '463038', text: 'Valio Eila 10 l box is cheaper (€0.66/L), but its order deadline (Thu 12 Nov 15:00) has passed and stock is unknown.' },
      { product_id: '462775', text: 'Arla lactose-free milk drink 1 l: only 51 in stock, not enough for 1000 L.' },
    ],
  },
}

const BUTTER: Omit<AgentRun, 'audit_id' | 'order'> = {
  request: {
    summary: '10 kg unsalted butter, delivered Monday 16 Nov',
    items: [{ query: 'unsalted butter', amount: 10, unit: 'kg', claims: [], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({ id: '464411', name_en: 'Valio butter 500 g unsalted', sales_unit: 'ST', claims: [], delivery_reliability: 1.0 }),
      quote: quote({
        price: 4.85, comparison_price: 9.7, comparison_unit: 'KG', available_amount: 640,
        order_cutoff: '2026-11-15T13:00:00+02:00',
      }),
      quantity: { sales_units: 20, explanation: '10 kg ÷ 0.5 kg per ST = 20 ST', needs_confirmation: false },
      line_total_cents: 9700,
      why: 'Exact match (unsalted, 500 g), in stock for Monday.',
      chosen: true,
    },
  ],
  decision: {
    outcome: 'ORDERED',
    reasons: [
      { code: 'WITHIN_MANDATE', severity: 'info', text: 'In stock, before the order deadline, and €97.00 is under the €1,000.00 auto-order limit.' },
    ],
    alternatives: [],
  },
}

const CREAM: Omit<AgentRun, 'audit_id' | 'order'> = {
  request: {
    summary: '40 L lactose-free whipping cream, delivered tomorrow (Sun 15 Nov)',
    items: [{ query: 'whipping cream', amount: 40, unit: 'L', claims: ['FREE_FROM_LACTOSE'], exclude_allergens: [] }],
  },
  lines: [
    {
      product: product({ id: '464194', name_en: 'Valio whipping cream 1 l UHT lactose free', sales_unit: 'ST', delivery_reliability: 1.0 }),
      quote: quote({
        price: 4.35, comparison_price: 4.35, comparison_unit: 'L', available_amount: 300,
        order_cutoff: '2026-11-13T15:00:00+02:00', available_date: '2026-11-17',
        flags: ['cutoff_passed', 'undeliverable'], orderable: false,
      }),
      quantity: { sales_units: 40, explanation: '40 L ÷ 1 L per ST = 40 ST', needs_confirmation: false },
      line_total_cents: 17400,
      why: 'Best match, but it cannot arrive on Sunday 15 Nov.',
      chosen: false,
    },
    {
      product: product({ id: '464699', name_en: 'Valio whipping cream 1 l lactose free, organic', sales_unit: 'ST', delivery_reliability: 0.947 }),
      quote: quote({
        price: 5.9, comparison_price: 5.9, comparison_unit: 'L', quantity_known: false,
        order_cutoff: '2026-11-13T15:00:00+02:00', available_date: '2026-11-17',
        flags: ['cutoff_passed', 'quantity_unknown'], orderable: false,
      }),
      quantity: { sales_units: 40, explanation: '40 L ÷ 1 L per ST = 40 ST', needs_confirmation: true },
      line_total_cents: 23600,
      why: 'Organic option; same deadline problem, and stock is unknown.',
      chosen: false,
    },
  ],
  decision: {
    outcome: 'REFUSED',
    reasons: [
      { code: 'CUTOFF_PASSED', severity: 'hard', text: 'The order deadline for Sunday 15 Nov delivery passed on Fri 13 Nov 15:00 for every matching product.' },
      { code: 'NO_DELIVERY_ON_DATE', severity: 'hard', text: 'Valio has no delivery for these products on Sundays.' },
    ],
    alternatives: [
      { product_id: '464194', text: 'Same cream (40 × 1 l, €174.00) delivered Tue 17 Nov if ordered by Mon 16 Nov 15:00.' },
      { product_id: '461273', text: 'Valio whipping cream 20 l novobox lactose free (2 boxes), delivered Tue 17 Nov.' },
    ],
  },
}

let seq = 0
const audit: AuditEntry[] = []
const wait = () => new Promise((r) => setTimeout(r, 600))

function log(summary: string, decision: AgentRun['decision'], outcome: string = decision.outcome) {
  const entry = { audit_id: `aud-mock-${++seq}`, at: new Date().toISOString(), summary, outcome, reasons: decision.reasons }
  audit.unshift(entry)
  return entry.audit_id
}

export const mockApi = {
  async health(): Promise<Health> {
    await wait()
    return { status: 'ok', valio_key_configured: true, gemini_key_configured: true, catalogue: { ready: true, products: 17546, error: null } }
  },

  async run(input: RunInput): Promise<AgentRun> {
    await wait()
    const text = input.text.toLowerCase()
    if (text.includes('error')) throw new Error('Request failed (500): mock backend error')
    const base = /1[ ,]?000/.test(text) ? MILK : /cream|tomorrow/.test(text) ? CREAM : BUTTER
    const run = structuredClone(base)
    const order =
      run.decision.outcome === 'REFUSED'
        ? null
        : { order_id: `ORD-MOCK-${seq + 1}`, status: run.decision.outcome === 'ORDERED' ? ('ORDERED' as const) : ('PENDING_APPROVAL' as const) }
    return { ...run, order, audit_id: log(run.request.summary, run.decision) }
  },

  async decide(orderId: string, action: 'approve' | 'reject'): Promise<ApprovalResult> {
    await wait()
    const approved = action === 'approve'
    const decision: ApprovalResult['decision'] = {
      outcome: approved ? 'ORDERED' : 'REFUSED',
      reasons: [{ code: approved ? 'HUMAN_APPROVED' : 'HUMAN_REJECTED', severity: 'info', text: approved ? 'Approved by the buyer.' : 'Rejected by the buyer.' }],
      alternatives: [],
    }
    log(`Order ${orderId} ${approved ? 'approved' : 'rejected'} by the buyer`, decision, approved ? 'ORDERED' : 'REJECTED')
    return { order_id: orderId, status: approved ? 'ORDERED' : 'REJECTED', decision }
  },

  async audit(): Promise<AuditEntry[]> {
    await wait()
    return [...audit]
  },
}
