import { tidyName } from './copy'
import { useCopy, type Copy } from './i18n'
import type { Line } from './types'
import './Compare.css'

// Compare options side by side (up to 4): every value comes from the response (quote, facts, product, confidence);
// a missing one says "not reported", never a guess. The best value in a row is marked (lowest price, total and CO₂,
// highest on-time and match). One tap chooses through the same path as the decision card.
type Row = { key: keyof Copy['UI']['result']['cmp']; value: (l: Line) => string | null; score?: (l: Line) => number | null; better?: 'low' | 'high' }

const rowsFor = (c: Copy): Row[] => {
  const t = c.UI.result
  const rel = (l: Line) => l.facts?.delivery_reliability ?? l.product.delivery_reliability
  const co2 = (l: Line) => l.facts?.carbon_kg_per_kg ?? l.product.carbon_kg_per_kg
  return [
    { key: 'price', value: (l) => (l.quote?.price != null ? `${c.price(l.quote.price)} / ${c.unitName(l.quote.sales_unit ?? l.product.sales_unit)}` : null), score: (l) => l.quote?.price ?? null, better: 'low' },
    { key: 'total', value: (l) => (l.line_total_cents != null ? c.money(l.line_total_cents) : null), score: (l) => l.line_total_cents, better: 'low' },
    { key: 'arrives', value: (l) => (l.quote?.available_date ? c.day(l.quote.available_date.slice(0, 10)) : null) },
    { key: 'orderBy', value: (l) => (l.quote?.order_cutoff ? c.dateTime(l.quote.order_cutoff) : null) },
    { key: 'stock', value: (l) => (!l.quote || !l.quote.quantity_known || l.quote.available_amount == null ? null : c.stock(l.quote.available_amount)) },
    { key: 'onTime', value: (l) => (rel(l) != null ? c.pct(rel(l)!) : null), score: rel, better: 'high' },
    { key: 'origin', value: (l) => (l.facts?.origin ? c.country(l.facts.origin) : null) },
    { key: 'co2', value: (l) => (co2(l) != null ? t.co2Value(c.count(co2(l)!)) : null), score: co2, better: 'low' },
    { key: 'match', value: (l) => (l.confidence != null ? c.pct(l.confidence) : null), score: (l) => l.confidence ?? null, better: 'high' },
    { key: 'diet', value: (l) => (l.product.claims.length ? l.product.claims.map((x) => x.toLowerCase().replace(/_/g, ' ')).join(', ') : t.noneListed) },
    {
      key: 'allergens',
      value: (l) => {
        const a = l.product.allergens
        if (!a) return null
        const parts = [...a.contains.map(c.allergen), ...(a.may_contain.length ? [t.mayContain(a.may_contain.map(c.allergen).join(', '))] : [])]
        return parts.length ? parts.join(', ') : t.noneListed
      },
    },
  ]
}

export function Compare({ lines, tags, onChoose, chooseLabel, busy, placing, onClose }: {
  lines: Line[] // up to 4, the agent's pick first
  tags: (l: Line) => string[]
  onChoose: ((l: Line) => void) | null // null: nothing can be chosen any more (already ordered)
  chooseLabel: (l: Line) => string
  busy: boolean
  placing: string | null
  onClose: () => void
}) {
  const c = useCopy()
  const t = c.UI.result
  const rows = rowsFor(c)
  const best = (r: Row): Set<Line> => {
    if (!r.score) return new Set()
    const scored = lines.map((l) => [l, r.score!(l)] as const).filter(([, v]) => v != null) as [Line, number][]
    if (scored.length < 2) return new Set()
    const top = r.better === 'low' ? Math.min(...scored.map(([, v]) => v)) : Math.max(...scored.map(([, v]) => v))
    return new Set(scored.filter(([, v]) => v === top).map(([l]) => l))
  }
  const bests = rows.map(best)
  return (
    <section className="cmp" aria-labelledby="cmp-title">
      <div className="cmp-head">
        <h2 className="title" id="cmp-title">
          {t.compareTitle}
        </h2>
        <button type="button" className="link" onClick={onClose}>
          {t.compareClose}
        </button>
      </div>
      <div className="cmp-grid" style={{ ['--cmp-rows' as string]: rows.length + 2 }}>
        {lines.map((l) => (
          <article key={l.product.id} className="cmp-card" aria-label={tidyName(l.product.name_en ?? l.product.id)}>
            <header className="cmp-card-head">
              {tags(l).length > 0 && (
                <span className="cmp-tags">
                  {tags(l).map((tag) => (
                    <span key={tag} className="cmp-tag">
                      {tag}
                    </span>
                  ))}
                </span>
              )}
              <h3 className="cmp-name">{tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)}</h3>
            </header>
            {rows.map((r, i) => {
              const v = r.value(l)
              return (
                <dl key={r.key} className={`cmp-row${bests[i].has(l) ? ' best' : ''}`}>
                  <dt>{t.cmp[r.key]}</dt>
                  <dd className={v == null ? 'cmp-missing' : 'num'}>{v ?? t.notReported}</dd>
                </dl>
              )
            })}
            <div className="cmp-choose">
              {onChoose && (
                <button type="button" className="btn plain accent-text" onClick={() => onChoose(l)} disabled={busy}>
                  {placing === l.product.id ? t.ordering : chooseLabel(l)}
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
