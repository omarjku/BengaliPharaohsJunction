import { useEffect, useRef, useState } from 'react'
import { decideOrder, getKeys, getOrder, MOCK, placeOrder } from './api'
import {
  errorText, flagLabel, formatCents, formatConfidence, formatDateTime, formatDay, formatEuro, outcomeView, resultView,
  stockText, type Tone,
} from './format'
import type { AgentRun, AlternativeOrder, Line, OrderResponse, Reason, Substitute } from './types'

type Props = {
  run: AgentRun
  requestedDate: string // the delivery date the run was for; a split order is placed for the same date
  onAction: () => void // an approve/reject/place finished (refresh the audit log)
  onBusy: (busy: boolean) => void
  onAnnounce: (headline: string) => void
}
type Action = 'approve' | 'reject' | 'place'

const STATUS_ICON: Record<Tone, string> = { good: '✓', warn: '!', bad: '✕', neutral: '–' }
const SEVERITY: Record<string, [Tone, string]> = { DECLINE: ['bad', '✕'], ASK_HUMAN: ['warn', '!'], INFO: ['neutral', 'i'] }
const CONFIDENCE_OK = 0.8

export function RunResult({ run, requestedDate, onAction, onBusy, onAnnounce }: Props) {
  const [busy, setBusy] = useState<Action | null>(null)
  const [result, setResult] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signOff, setSignOff] = useState<string | null>(null) // 'Approved by Chef Aino' after a human decided
  const heading = useRef<HTMLHeadingElement>(null)

  // The front door's verdict wins over the agent's own: it re-checks with fresh quotes.
  const order = result ?? run.order
  const decision = order?.decision ?? run.decision
  const [tone, title] = order ? resultView(order.status) : outcomeView(run.decision.outcome)
  // The headline is the top reason (or the sign-off); the list below holds the rest, so nothing repeats.
  const lead = signOff ? null : (decision.reasons[0] ?? null)
  const why = signOff
    ? `${signOff}.`
    : (lead?.message ?? (order?.status === 'confirmed' ? 'Within your mandate, so the agent ordered it at fixed prices.' : title))
  const listed = lead ? decision.reasons.slice(1) : decision.reasons
  const awaitingApproval = order?.status === 'pending_approval' && order.order_id !== null
  const canDecide = MOCK || Boolean(getKeys().approverKey)

  useEffect(() => {
    onAnnounce(`${title}. ${why}`)
    heading.current?.focus()
  }, [title, why, result, onAnnounce])

  async function act(action: Action) {
    if (action !== 'place' && !order?.order_id) return
    setBusy(action)
    onBusy(true)
    setError(null)
    try {
      setResult(
        action === 'place'
          ? await placeOrder({
              requested_date: requestedDate,
              lines: (order?.alternative_order?.lines ?? []).map((l) => ({ product_id: l.product_id, quantity: l.quantity ?? 0 })),
            })
          : await decideOrder(order!.order_id!, action),
      )
      if (action !== 'place') {
        const verb = action === 'approve' ? 'Approved' : 'Rejected'
        const who = await getOrder(order!.order_id!).then((o) => o.signed_off_by, () => null) // name is a nicety
        setSignOff(who ? `${verb} by ${who}` : verb)
      } else {
        setSignOff(null)
      }
      onAction()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
      onBusy(false)
    }
  }

  const lines = [...run.lines.filter((l) => l.chosen), ...run.lines.filter((l) => !l.chosen)]
  const subs = order?.substitutes ?? []
  const nameOf = (id: string) =>
    order?.lines.find((l) => l.product_id === id)?.name ?? run.lines.find((l) => l.product.id === id)?.product.name_en ?? id

  return (
    <section className="stack" aria-label="Agent result">
      <div className={`card decision ${tone}`}>
        <div className="decision-top">
          <span className={`pill chip-lg tone-${tone}`}>
            <span aria-hidden="true">{STATUS_ICON[tone]}</span> {title}
          </span>
          {run.decision.confidence != null && <ConfidencePill value={run.decision.confidence} />}
        </div>
        <h2 ref={heading} tabIndex={-1} className="decision-why">
          {why}
        </h2>
        {lead?.suggested_fix && <p className="why-fix">{lead.suggested_fix}</p>}
        <p className="asked">
          You asked for:{' '}
          {run.request.items
            .map((it) =>
              [[it.amount, it.unit, it.query].filter((x) => x !== null).join(' '), ...it.claims.map(humanize)].join(', '),
            )
            .join('; ') || run.request.summary}
        </p>
        {order?.order_id && (tone === 'good' || awaitingApproval) && (
          <p className="order-line">
            Order <code>{order.order_id}</code> · <strong>{formatCents(order.total_cents)}</strong> net of VAT
          </p>
        )}
        {listed.length > 0 && (
          <div className="stack-sm">
            <h3 className="label">{signOff ? 'Original reasons' : 'Also'}</h3>
            <ul className="reasons">
              {listed.map((r, i) => (
                <ReasonItem key={i} reason={r} muted={signOff !== null} />
              ))}
            </ul>
          </div>
        )}
        {awaitingApproval && (
          <div className="stack-sm">
            {!canDecide && <p className="small muted">Enter the approver key in Keys to approve.</p>}
            <div className="actions">
              <button type="button" className="btn" onClick={() => act('approve')} disabled={busy !== null || !canDecide}>
                {busy === 'approve' ? 'Approving…' : 'Approve'}
              </button>
              <button type="button" className="btn danger" onClick={() => act('reject')} disabled={busy !== null || !canDecide}>
                {busy === 'reject' ? 'Rejecting…' : 'Reject'}
              </button>
            </div>
          </div>
        )}
        {subs.length === 0 && decision.alternatives.length > 0 && (
          <div className="stack-sm">
            <h3 className="label">Alternatives</h3>
            <ul className="stack-sm small">
              {decision.alternatives.map((a, i) => (
                <li key={i}>
                  {a.summary} <span className="muted">#{a.product_id}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      {lines.length > 0 && (
        <div className="card">
          <h2 className="card-title">Products checked</h2>
          <ul className="products">
            {lines.map((l) => (
              <ProductRow key={`${l.product.id}-${l.chosen}`} line={l} />
            ))}
          </ul>
        </div>
      )}

      {subs.length > 0 && <Substitutes subs={subs} nameOf={nameOf} />}
      {order?.alternative_order && (
        <SplitProposal alt={order.alternative_order} busy={busy === 'place'} disabled={busy !== null} onUse={() => act('place')} />
      )}
    </section>
  )
}

const humanize = (code: string) => code.toLowerCase().replace(/_/g, ' ')
const percent = (x: number) => `${Math.round(x * 100)}%`

function ReasonItem({ reason: r, muted }: { reason: Reason; muted: boolean }) {
  const [tone, icon] = SEVERITY[r.severity] ?? ['neutral', 'i']
  return (
    <li className={`reason${muted ? ' muted' : ''}`}>
      <span className={`icon pill tone-${tone}`} aria-hidden="true">
        {icon}
      </span>
      <div>
        <p>{r.message}</p>
        {r.suggested_fix && <p className="fix">{r.suggested_fix}</p>}
      </div>
    </li>
  )
}

// Gemini Decisions API: how sure it is that a product is what the buyer asked for (floored like the backend).
function ConfidencePill({ value }: { value: number }) {
  const ok = value >= CONFIDENCE_OK
  return <span className={`pill tone-${ok ? 'good' : 'warn'}`}>Gemini {formatConfidence(value)}</span>
}

function availability(line: Line): [string, string] {
  const q = line.quote
  if (!q) return ['bad', 'Not quoted by Valio']
  const bad = q.flags.filter((f) => f !== 'quantity_unknown')
  if (bad.length) return ['bad', bad.map(flagLabel).join(' · ')]
  const parts = [
    q.flags.includes('quantity_unknown') ? 'Stock unknown' : q.available_amount !== null ? stockText(q.available_amount) : 'Stock unknown',
  ]
  if (q.order_cutoff) parts.push(`order by ${formatDateTime(q.order_cutoff)}`)
  if (q.available_date) parts.push(`arrives ${formatDay(q.available_date.slice(0, 10))}`)
  return [q.flags.includes('quantity_unknown') ? 'warn' : '', parts.join(', ')]
}

function FactTags({ reliability, carbon, origin, extra = [] }: { reliability?: number | null; carbon?: number | null; origin?: string | null; extra?: string[] }) {
  const tags = [
    reliability != null ? `on time ${percent(reliability)}` : null,
    origin ? `origin ${origin.toUpperCase()}` : null,
    carbon != null ? `${carbon.toLocaleString('en-US')} kg CO₂/kg` : null,
    ...extra,
  ].filter((t): t is string => t !== null)
  if (!tags.length) return null
  return (
    <ul className="tags" aria-label="Product facts">
      {tags.map((t) => (
        <li key={t} className="tag">
          {t}
        </li>
      ))}
    </ul>
  )
}

function ProductRow({ line }: { line: Line }) {
  const { product: p, quote: q, quantity } = line
  const unit = quantity?.sales_unit || p.sales_unit || 'units'
  const [availTone, availText] = availability(line)
  const facts = line.facts
  return (
    <li className={`product ${line.chosen ? 'chosen' : 'other'}`}>
      <div className="product-main">
        <p className="product-name">
          {line.chosen && <span className="pill tone-accent">Chosen</span>} {p.name_en ?? p.name_fi ?? p.id}
          <span className="muted small"> · {[p.brand, `#${p.id}`].filter(Boolean).join(' · ')}</span>
        </p>
        <p className={`avail ${availTone}`}>{availText}</p>
        {line.confidence != null && (
          <p className="conf">
            <ConfidencePill value={line.confidence} />
            {line.confidence < CONFIDENCE_OK && <strong className="avail warn">Gemini isn’t sure this is what you asked for.</strong>}
            {line.confidence_reason && <span className="muted">{line.confidence_reason}</span>}
          </p>
        )}
        <p className="small">{line.why}</p>
        <FactTags
          reliability={facts ? facts.delivery_reliability : p.delivery_reliability}
          carbon={facts ? facts.carbon_kg_per_kg : p.carbon_kg_per_kg}
          origin={facts?.origin}
          extra={quantity?.needs_confirmation ? ['quantity needs your confirmation'] : []}
        />
        {quantity && <p className="small muted">{quantity.explanation}</p>}
      </div>
      <div className="product-side">
        <strong>{quantity === null ? 'Quantity not given' : quantity.quantity !== null ? `${quantity.quantity.toLocaleString('en-US')} × ${unit}` : 'Quantity unclear'}</strong>
        {line.line_total_cents !== null && <strong>{formatCents(line.line_total_cents)}</strong>}
        <span className="small muted">{q?.price != null ? `${formatEuro(q.price)} / ${unit}` : 'price unknown'}</span>
      </div>
    </li>
  )
}

const TIER: Record<string, [string, string]> = { best: ['good', 'Best'], better: ['accent', 'Better'], good: ['neutral', 'Good'] }

// Up to 3 allergen-safe substitutes per refused line, best first (the backend's order is kept).
function Substitutes({ subs, nameOf }: { subs: Substitute[]; nameOf: (id: string) => string }) {
  const groups = [...new Set(subs.map((s) => s.replaces))]
  return (
    <div className="card stack">
      <h2 className="card-title">Substitutes</h2>
      {groups.map((id) => (
        <div key={id} className="stack-sm">
          <h3 className="label">Instead of {nameOf(id)}</h3>
          <ul className="subs">
            {subs
              .filter((s) => s.replaces === id)
              .map((s) => {
                const [tone, label] = TIER[s.tier] ?? ['neutral', s.tier]
                return (
                  <li key={s.product_id} className="sub">
                    <span className={`pill tone-${tone}`}>
                      {label}
                    </span>
                    <p className="sub-name">
                      {s.name} <span className="muted small">#{s.product_id}</span>
                    </p>
                    <p className="small">
                      <strong>Why it’s safe:</strong> {s.why_safe}
                    </p>
                    <p>
                      <strong>{s.unit_price_cents !== null ? formatCents(s.unit_price_cents) : 'Price unknown'}</strong>
                      <span className="small muted"> / {s.unit ?? 'unit'} net</span>
                    </p>
                    <FactTags
                      reliability={s.reliability}
                      origin={s.origin}
                      extra={[s.available !== null ? stockText(s.available) : 'stock unknown', ...(s.reliability === null ? ['no delivery record'] : [])]}
                    />
                  </li>
                )
              })}
          </ul>
        </div>
      ))}
    </div>
  )
}

function SplitProposal({ alt, busy, disabled, onUse }: { alt: AlternativeOrder; busy: boolean; disabled: boolean; onUse: () => void }) {
  return (
    <div className="card">
      <h2 className="card-title">Split order proposal</h2>
      <p className="small muted">{alt.summary}</p>
      <table className="split-table">
        <thead>
          <tr>
            <th scope="col">Product</th>
            <th scope="col" className="num">
              Quantity
            </th>
            <th scope="col" className="num">
              Line total
            </th>
          </tr>
        </thead>
        <tbody>
          {alt.lines.map((l) => (
            <tr key={l.product_id}>
              <td>
                {l.name}
                {l.replaces && <span className="muted"> · substitute</span>}
              </td>
              <td className="num">
                {l.quantity?.toLocaleString('en-US')} × {l.unit ?? 'units'}
              </td>
              <td className="num">{l.line_total_cents !== null ? formatCents(l.line_total_cents) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="split-total">
        <p>
          Total <strong>{formatCents(alt.total_cents)}</strong> <span className="small muted">net of VAT</span>
        </p>
        <button type="button" className="btn" onClick={onUse} disabled={disabled}>
          {busy ? 'Placing…' : 'Use this order'}
        </button>
      </div>
    </div>
  )
}
