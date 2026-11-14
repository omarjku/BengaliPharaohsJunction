// Shapes of the backend responses the UI reads. If the backend renames a field,
// fix it here (and in api.ts); components only import these types.

export type Outcome = 'ORDERED' | 'NEEDS_APPROVAL' | 'REFUSED'

export type Reason = { code: string; severity: string; text: string }
export type Alternative = { product_id: string; text: string }
export type Decision = { outcome: Outcome; reasons: Reason[]; alternatives: Alternative[] }

export type RequestItem = {
  query: string
  amount: number
  unit: string
  claims: string[]
  exclude_allergens: string[]
}

export type Product = {
  id: string
  name_en: string | null
  name_fi: string | null
  brand: string | null
  sales_unit: string
  claims: string[]
  allergens: { contains: string[]; may_contain: string[]; free_from: string[] }
  delivery_reliability: number | null
  carbon_kg_per_kg: number | null
}

export type Quote = {
  price: number | null // euros per sales unit, as sent by the backend (display only)
  comparison_price: number | null
  comparison_unit: string | null
  available_amount: number | null
  quantity_known: boolean
  order_cutoff: string | null // ISO datetime
  available_date: string | null // YYYY-MM-DD
  flags: string[]
  orderable: boolean
}

export type Line = {
  product: Product
  quote: Quote
  quantity: { sales_units: number; explanation: string; needs_confirmation: boolean }
  line_total_cents: number | null
  why: string
  chosen: boolean
}

export type AgentRun = {
  request: { summary: string; items: RequestItem[] }
  lines: Line[]
  decision: Decision
  order: { order_id: string; status: 'ORDERED' | 'PENDING_APPROVAL' } | null
  audit_id: string
}

export type RunInput = { text: string; requested_date: string; buyer_id: string }

export type ApprovalResult = {
  order_id: string
  status: 'ORDERED' | 'REJECTED' | 'REFUSED'
  decision: Decision
}

export type AuditEntry = { audit_id: string; at: string; summary: string; outcome: string; reasons: Reason[] }

export type Health = {
  status: string
  valio_key_configured: boolean
  gemini_key_configured: boolean
  catalogue: { ready: boolean; products: number; error: string | null }
}
