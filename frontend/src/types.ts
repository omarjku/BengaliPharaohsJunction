// Shapes of the backend responses the UI reads, mirroring contracts/trade_contracts (Decision, Reason,
// AuditEntry) and backend/app (catalogue product, valio._merge quote, quantity.resolve, orders responses).
// Codes and statuses stay as the backend sends them; chef-facing wording lives in the components.

export type Outcome = 'AUTO' | 'ASK_HUMAN' | 'DECLINE'
export type Severity = 'INFO' | 'ASK_HUMAN' | 'DECLINE'
export type FactValue = string | number | boolean | null

export type Reason = {
  code: string
  severity: Severity
  message: string
  facts: Record<string, FactValue>
  suggested_fix: string | null
  product_id: string | null
}
export type Alternative = { product_id: string; summary: string }
export type Decision = {
  contract_version: string
  request_id: string
  outcome: Outcome
  reasons: Reason[] // highest severity first
  primary_reason: Reason | null
  confidence: number | null
  alternatives: Alternative[]
  rules_version: string
  decided_at: string // ISO datetime
}

export type RequestItem = {
  query: string
  amount: number | null
  unit: string | null
  claims: string[]
  exclude_allergens: string[]
}

// Catalogue product (backend/app/catalogue.py); only the fields the UI reads.
export type Product = {
  id: string
  name_en: string | null
  name_fi: string | null
  brand: string | null
  sales_unit: string | null
  claims: string[]
  allergens: { contains: string[]; may_contain: string[]; free_from: string[] }
  delivery_reliability: number | null
  carbon_kg_per_kg: number | null
}

// valio._merge: one product's live availability + price (euro floats, display only).
export type Quote = {
  product_id: string
  logistic_model: string | null
  available_amount: number | null
  quantity_known: boolean
  available_date: string | null
  order_cutoff: string | null // ISO datetime
  sales_unit: string | null
  price: number | null // net euros per sales unit
  price_with_tax: number | null
  comparison_price: number | null
  comparison_unit: string | null
  flags: string[]
  orderable: boolean
  fetched_at: string
}

// quantity.resolve: buyer amount -> sales units. quantity null = couldn't convert (needs_confirmation).
export type QuantityResolution = {
  product_id: string
  requested: { amount: number; unit: string }
  sales_unit: string
  quantity: number | null
  per_sales_unit: number | null
  delivered: number | null
  over_delivery: number | null
  rounded_up: boolean
  confidence: 'high' | 'medium' | 'none'
  needs_confirmation: boolean
  explanation: string
}

export type Line = {
  product: Product
  quote: Quote | null
  quantity: QuantityResolution | null
  line_total_cents: number | null
  why: string
  chosen: boolean
}

export type OrderStatus = 'confirmed' | 'pending_approval' | 'refused' | 'rejected'

// One line as re-checked at the front door (gate.check_line info).
export type OrderLine = {
  product_id: string
  name: string
  quantity: number | null
  unit: string | null
  unit_price_cents: number | null
  line_total_cents: number | null
}

// POST /api/orders and /api/orders/{id}/approve|reject.
export type OrderResponse = {
  order_id: string | null // null when refused (nothing stored)
  status: OrderStatus
  audit_id: string
  total_cents: number
  lines: OrderLine[]
  decision: Decision
  rejected_options: { product_id: string; reasons: Reason[] }[]
}

export type AgentRun = {
  request: { summary: string; items: RequestItem[] }
  lines: Line[]
  decision: Decision
  order: OrderResponse | null
  audit_id: string
}

export type RunInput = { text: string; requested_date: string; buyer_id: string }

// Contract AuditEntry (GET /api/audit, oldest first).
export type AuditEntry = {
  contract_version: string
  id: string
  timestamp: string
  actor: string // 'buyer_agent', 'valio_front_door', 'human:<name>:approve' ...
  input: {
    request: {
      id: string
      buyer_id: string
      text: string
      items: { name: string; quantity: number | null; unit: string | null }[]
      needed_by: string | null
      created_at: string
    }
    mandate: unknown
    quotes: unknown[]
  }
  decision: Decision
  rejected_options: { product_id: string; reasons: Reason[] }[]
}

export type Health = {
  status: string
  valio_key_configured: boolean
  gemini_key_configured: boolean
  catalogue: { ready: boolean; products: number; error: string | null }
}
