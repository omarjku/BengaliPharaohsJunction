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
  partial_stock: 'Only part of the amount in stock',
  unknown_product: 'Product not found at Valio',
}

export const flagLabel = (flag: string) => FLAG_LABELS[flag] ?? flag.replace(/_/g, ' ')

// Next Monday in local time (a week ahead if today is Monday), as YYYY-MM-DD.
export function nextMonday(from = new Date()): string {
  const d = new Date(from)
  d.setDate(d.getDate() + (((8 - d.getDay()) % 7) || 7))
  return [d.getFullYear(), d.getMonth() + 1, d.getDate()].map((n) => String(n).padStart(2, '0')).join('-')
}

export const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.')
