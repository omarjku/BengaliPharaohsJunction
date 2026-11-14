// Mock backend for VITE_MOCK=1 / ?mock=1 (dev only). Products are real catalogue entries; prices,
// stock and cut-offs are illustrative. Which fixture you get depends on the request text:
//   contains "1000" / "1 000" / "1,000"  -> ASK_HUMAN, order pending_approval (the lactose-free milk case)
//   contains "cream" or "tomorrow"       -> refused at the front door (cut-off passed)
//   contains "error"                     -> a failed request (to see the error state)
//   anything else                        -> AUTO, order confirmed (small butter order)
import type {
  AgentRun, Alternative, AuditEntry, Decision, Health, Line, OrderResponse, OrderStatus, Product, Quote,
  QuantityResolution, Reason, RunInput,
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

const decision = (outcome: Decision['outcome'], reasons: Reason[], alternatives: Alternative[] = []): Decision => ({
  contract_version: '0.2', request_id: 'req-mock', outcome, reasons, primary_reason: reasons[0] ?? null,
  confidence: 0.9, alternatives, rules_version: 'mock', decided_at: NOW,
})

type Fixture = { request: AgentRun['request']; lines: Line[]; decision: Decision; status: OrderStatus }

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
        product_id: '463335', price: 1.4, comparison_price: 1.4, comparison_unit: 'L', available_amount: 2400,
        order_cutoff: '2026-11-15T13:00:00+02:00',
      }),
      quantity: qty('463335', 1000, 'L', 'ST', 1000, 1, '1,000 L ÷ 1 L per ST (1 LTR per ST) = 1,000 ST.'),
      line_total_cents: 140000,
      why: 'Lactose free, 1 l cartons in stock for Monday, best delivery reliability (100 %).',
      chosen: true,
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
      reason('LINE_OVER_CAP', 'ASK_HUMAN', 'The Valio Eila® 3 % milk drink 1 l lactose free line is €1,400.00 (net of VAT), above your €300.00 per-line cap.', {
        product_id: '463335', suggested_fix: 'Approve, or reduce the quantity.', facts: { line_total_cents: 140000, cap_cents: 30000 },
      }),
    ],
    [{ product_id: '462775', summary: 'Arla lactose-free milk drink 1 l: only 51 in stock, not enough for 1000 L.' }],
  ),
  status: 'pending_approval',
}

const BUTTER: Fixture = {
  request: {
    summary: '10 kg unsalted butter, delivered Monday 16 Nov',
    items: [{ query: 'unsalted butter', amount: 10, unit: 'kg', claims: [], exclude_allergens: [] }],
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

const orders = new Map<string, { buyer: string; res: OrderResponse }>()

export const mockApi = {
  async health(): Promise<Health> {
    await wait()
    return { status: 'ok', valio_key_configured: true, gemini_key_configured: true, catalogue: { ready: true, products: 17546, error: null } }
  },

  async run(input: RunInput): Promise<AgentRun> {
    await wait()
    const text = input.text.toLowerCase()
    if (text.includes('error')) throw new Error('Request failed (500): mock backend error')
    const f = structuredClone(/1[ ,]?000/.test(text) ? MILK : /cream|tomorrow/.test(text) ? CREAM : BUTTER)
    const chosen = f.lines.filter((l) => l.chosen)
    const order: OrderResponse = {
      order_id: f.status === 'refused' ? null : `00000000-0000-4000-8000-${String(seq + 1).padStart(12, '0')}`,
      status: f.status,
      audit_id: log('valio_front_door', input.buyer_id, `Order via Valio front door: ${f.request.summary}`, f.decision),
      total_cents: chosen.reduce((a, l) => a + (l.line_total_cents ?? 0), 0),
      lines: chosen.map((l) => ({
        product_id: l.product.id, name: l.product.name_en ?? l.product.id, quantity: l.quantity.quantity,
        unit: l.product.sales_unit, unit_price_cents: l.quote?.price != null ? Math.round(l.quote.price * 100) : null,
        line_total_cents: l.line_total_cents,
      })),
      decision: f.decision,
      rejected_options: [],
    }
    if (order.order_id) orders.set(order.order_id, { buyer: input.buyer_id, res: order })
    return { request: f.request, lines: f.lines, decision: f.decision, order, audit_id: log('buyer_agent', input.buyer_id, input.text, f.decision) }
  },

  async decide(orderId: string, action: 'approve' | 'reject', approver: string): Promise<OrderResponse> {
    await wait()
    const o = orders.get(orderId)
    if (!o) throw new Error('Request failed (404): Unknown order id')
    if (o.res.status !== 'pending_approval') throw new Error(`Request failed (409): Order is ${o.res.status}, not pending approval`)
    const status: OrderStatus = action === 'approve' ? 'confirmed' : 'rejected'
    const d = o.res.decision // the backend re-runs the gate on approve; the reasons the human saw stay on it
    o.res = { ...o.res, status, decision: d, audit_id: log(`human:${approver}:${action}`, o.buyer, `Order ${orderId}`, d) }
    return o.res
  },

  async audit(buyerId: string): Promise<AuditEntry[]> {
    await wait()
    return audit.filter((e) => e.input.request.buyer_id === buyerId)
  },
}
