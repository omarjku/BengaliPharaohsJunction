// Display helpers. Money totals arrive as integer cents and are formatted with integer math only.

export function formatCents(cents: number): string {
  const abs = Math.abs(cents)
  const euros = Math.floor(abs / 100).toLocaleString('en-US')
  return `${cents < 0 ? '−' : ''}€${euros}.${String(abs % 100).padStart(2, '0')}`
}

// Unit prices arrive as euro numbers from the backend; this only formats them, no arithmetic.
export const formatEuro = (n: number) =>
  new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(n)

const HELSINKI = 'Europe/Helsinki'

export const formatDateTime = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: HELSINKI,
  }).format(new Date(iso))

// "YYYY-MM-DD" is a calendar date: format it in UTC so it never shifts a day.
export const formatDay = (ymd: string) =>
  new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${ymd}T00:00:00Z`),
  )

const FLAG_LABELS: Record<string, string> = {
  cutoff_passed: 'Order deadline passed',
  quantity_unknown: 'Stock unknown (supplier delivers)',
  undeliverable: 'Cannot be delivered on the requested date',
  out_of_stock: 'Out of stock',
  sales_block: 'Sales blocked at Valio',
  unknown_product: 'Product not found at Valio',
}

export const flagLabel = (flag: string) => FLAG_LABELS[flag] ?? flag.replace(/_/g, ' ')

// Next Monday in Helsinki (a week ahead if it is Monday there), as YYYY-MM-DD.
export function nextMonday(from = new Date()): string {
  const [y, m, d] = new Intl.DateTimeFormat('en-CA', { timeZone: HELSINKI }).format(from).split('-').map(Number)
  const day = new Date(Date.UTC(y, m - 1, d))
  day.setUTCDate(d + ((8 - day.getUTCDay()) % 7 || 7))
  return day.toISOString().slice(0, 10)
}

export const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.')

// Chef-facing wording for backend codes. Unknown values fall back to the raw code, never a blank page.
export type Tone = 'good' | 'warn' | 'bad' | 'neutral'
const OUTCOME_VIEW: Record<string, [Tone, string]> = {
  AUTO: ['good', 'Ordered'],
  ASK_HUMAN: ['warn', 'Needs your OK'],
  DECLINE: ['bad', 'Refused'],
}
const RESULT_VIEW: Record<string, [Tone, string]> = {
  confirmed: ['good', 'Ordered'],
  pending_approval: ['warn', 'Needs your OK'],
  refused: ['bad', 'Refused at Valio’s front door'],
  rejected: ['neutral', 'Rejected: nothing was ordered'],
}
export const outcomeView = (o: string): [Tone, string] => OUTCOME_VIEW[o] ?? ['neutral', o]
export const resultView = (s: string): [Tone, string] => RESULT_VIEW[s] ?? ['neutral', s]
