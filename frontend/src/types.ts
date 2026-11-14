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

// Room 1: static facts about the product, shown when present.
export type LineFacts = { delivery_reliability: number | null; carbon_kg_per_kg: number | null; origin: string | null }

export type Line = {
  product: Product
  quote: Quote | null
  quantity: QuantityResolution | null
  line_total_cents: number | null
  why: string
  chosen: boolean
  confidence?: number | null // Gemini Decisions API: P(this product is what the buyer asked for)
  confidence_reason?: string | null
  facts?: LineFacts
  item?: number // index into the request's items (menu: into ingredients)
  dishes?: string[] // menu runs: the dishes this line is for
}

// gate._substitutes: up to 3 allergen-safe substitutes per refused line, best first.
export type Substitute = {
  product_id: string
  replaces: string
  tier: 'best' | 'better' | 'good'
  why_safe: string
  name: string
  unit: string | null
  unit_price_cents: number | null
  reliability: number | null
  origin: string | null
  available: number | null // null = unknown
}

// gate._alternative_order: a split proposal when stock is short. Never automatic; re-POST its lines to order.
export type AlternativeOrder = {
  lines: (OrderLine & { replaces?: string; tier?: Substitute['tier'] })[]
  total_cents: number
  summary: string
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
  substitutes?: Substitute[] // absent on reject responses
  alternative_order?: AlternativeOrder | null
}

export type AgentRun = {
  request: { summary: string; items: RequestItem[] }
  lines: Line[]
  decision: Decision
  order: OrderResponse | null
  audit_id: string
}

// POST /api/agent/menu: a proposed cart for a menu (always ASK_HUMAN; nothing is ordered until order_lines are posted).
export type MenuIngredient = { name: string; per_cover: number | null; unit: string | null; assumption: string | null }
export type MenuRun = {
  menu: { dishes: { name: string; ingredients: MenuIngredient[] }[] }
  assumptions: { ingredient: string; dish: string; per_cover: number; unit: string | null; text: string }[]
  ingredients: (RequestItem & { dishes: string[] })[]
  lines: Line[]
  cart_total_cents: number
  order_lines: { product_id: string; quantity: number }[]
  decision: Decision
  audit_id: string
}
export type MenuInput = { menu_text: string; covers: number; requested_date: string }

// Rules (mandate). Money values are net-of-VAT cents; allergen values are GS1 codes ('AP') or plain words ('gluten').
export type HardRule = { kind: string; value: string | number; scope: string; source_text: string | null }
export type Mandate = {
  contract_version: string
  id: string
  buyer_id: string
  hard_rules: HardRule[]
  uncertainty_policy: 'ask' | 'decline' | 'approve'
  guidance: { text: string; scope: string }[]
  open_questions: { question: string; why: string | null }[]
  blocklist: string[]
  per_line_cap_cents: number
  weekly_budget_cents: number | null
  expires_at: string | null
}
export type RuleChange = {
  field: string
  before: unknown
  after: unknown
  change: 'tighter' | 'looser' | 'changed'
  text: string
  needs_confirmation: boolean
}
export type CompileResult = {
  proposed_mandate: Mandate
  diff_from_current: RuleChange[]
  open_questions: { question: string; why: string | null }[]
  assumptions: string[]
  used_fallback: boolean
  injection_flagged: boolean
}
export type SaveResult = { mandate: Mandate; changes: RuleChange[]; audit_id: string }

// POST /api/agent/ask: one box for everything (backend/app/ask.py). The intent says which body came back; a question
// (guests, which delivery day, unclear) comes back with no cart. requested_date is the date used, from the words or the
// override; urgent_options are suggestions when the chef needs it sooner (walk-in, Click & Collect, next delivery).
export type UrgentOption = {
  kind: 'walk_in' | 'click_and_collect' | 'next_delivery' | string
  label: string
  text: string
  address?: string
  hours?: string
  phone?: string
  assumption: boolean
}
type AskMeta = {
  requested_date?: string | null
  date_source?: 'text' | 'request' | null
  covers?: number | null
  urgent_options?: UrgentOption[] | null
  speak?: string | null // one sentence to read back, in the request's language
  conversation_id?: string | null // set when the question can be answered with a follow_up
}
export type AskInput = { text: string; requested_date?: string; follow_up?: { to: string; answer: string } }
export type AskResponse =
  | (AskMeta & { intent: 'order'; question?: null } & AgentRun)
  | (AskMeta & { intent: 'menu'; question?: null } & MenuRun)
  | (AskMeta & { intent: 'order' | 'menu' | 'unclear'; question: string; decision?: Decision; audit_id?: string })

export type RunInput = { text: string; requested_date: string; buyer_id?: string }
export type OrderInput = { requested_date: string; lines: { product_id: string; quantity: number }[] }

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
