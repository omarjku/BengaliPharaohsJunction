type PackQuantity = {
  quantity: number | null
  per_sales_unit: number | null
  requested: { amount: number; unit: string }
  sales_unit: string
}

type PackFallback = { quantity: number | null; unit: string | null }

const number = (value: number) => String(Math.round(value * 1000) / 1000)

const sustainabilityLabels: Record<string, string> = {
  GOODS_FROM_FINLAND_BLUE_SWAN: 'Blue Swan',
  MADE_IN_FINLAND_FLAG_WITH_KEY: 'Made in Finland',
  FINNISH_HEART_SYMBOL: 'Finnish Heart',
  EU_ORGANIC_FARMING: 'EU Organic',
  SVANEN: 'Svanen',
  RAINFOREST_ALLIANCE: 'Rainforest Alliance',
  EU_ECO_LABEL: 'EU Ecolabel',
  MARINE_STEWARDSHIP_COUNCIL_LABEL: 'MSC',
  FAIR_TRADE_MARK: 'Fairtrade',
  MSC: 'MSC',
}

export function formatCartPack(quantity: PackQuantity | null | undefined, fallback?: PackFallback, formatNumber = number): string {
  if (quantity?.quantity != null && quantity.per_sales_unit != null && quantity.requested.unit)
    return `${formatNumber(quantity.quantity)} × ${formatNumber(quantity.per_sales_unit)} ${quantity.requested.unit}`
  if (quantity?.quantity != null && quantity.sales_unit) return `${formatNumber(quantity.quantity)} ${quantity.sales_unit}`
  if (fallback?.quantity != null && fallback.unit) return `${formatNumber(fallback.quantity)} ${fallback.unit}`
  return '—'
}

export function countryFlag(code: string): string {
  const country = code.toUpperCase()
  if (!/^[A-Z]{2}$/.test(country)) return ''
  return String.fromCodePoint(...[...country].map((letter) => 127_397 + letter.charCodeAt(0)))
}

export function formatSustainabilityLabel(label: string): string {
  return sustainabilityLabels[label] ?? label.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())
}
