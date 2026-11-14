import { useEffect, useRef, useState } from 'react'
import { decideOrder, getKeys, getOrder, MOCK, placeOrder } from './api'
import {
  errorText, flagLabel, formatCents, formatConfidence, formatDateTime, formatDay, formatEuro, outcomeView, resultView, stockText,
} from './format'
import type { AgentRun, AlternativeOrder, Line, OrderResponse, Substitute } from './types'

type Props = {
  run: AgentRun
  requestedDate: string // the delivery date the run was for; a split order is placed for the same date
  onAction: () => void // an approve/reject finished (refresh the audit log)
  onBusy: (busy: boolean) => void
  onAnnounce: (headline: string) => void
}

export function RunResult({ run, ...rest }: Props) {
  const chosen = run.lines.filter((l) => l.chosen)
  const others = run.lines.filter((l) => !l.chosen)
  const totals = chosen.map((l) => l.line_total_cents)
  const total = totals.every((c) => c !== null) ? totals.reduce<number>((a, c) => a + (c ?? 0), 0) : null

  return (
    <section className="results" aria-label="Agent result">
      <div className="card">
        <h2>What the agent understood</h2>
        <p>{run.request.summary}</p>
        <ul className="items">
          {run.request.items.map((it, i) => (
            <li key={i}>
              {[it.amount, it.unit, it.query].filter((x) => x !== null).join(' ')}
              {it.claims.length > 0 && <span className="muted"> · {it.claims.map(humanize).join(', ')}</span>}
              {it.exclude_allergens.length > 0 && <span className="muted"> · without {it.exclude_allergens.join(', ')}</span>}
            </li>
          ))}
        </ul>
      </div>

      <DecisionCard run={run} {...rest} />

      {chosen.length > 0 && (
        <div className="card">
          <h2>Selected</h2>
          <ul className="lines">
            {chosen.map((l) => (
              <LineItem key={l.product.id} line={l} />
            ))}
          </ul>
          {total !== null && (
            <p className="total">
              Total <strong>{formatCents(total)}</strong> <span className="muted">(net of VAT)</span>
            </p>
          )}
        </div>
      )}

      {others.length > 0 && (
        <div className="card">
          <h2>Considered, not chosen</h2>
          <ul className="lines">
            {others.map((l) => (
              <LineItem key={l.product.id} line={l} />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

const humanize = (code: string) => code.toLowerCase().replace(/_/g, ' ')

function LineItem({ line }: { line: Line }) {
  const { product: p, quote: q, quantity } = line
  const unit = quantity?.sales_unit || p.sales_unit || 'units'
  return (
    <li className="line">
      <p className="line-name">
        <strong>{p.name_en ?? p.name_fi ?? p.id}</strong> <span className="muted">#{p.id}</span>
      </p>
      <Confidence value={line.confidence ?? null} reason={line.confidence_reason ?? null} />
      <p>{line.why}</p>
      <dl>
        <dt>Quantity</dt>
        <dd>
          {quantity === null ? (
            'Quantity not given'
          ) : (
            <>
              {quantity.quantity !== null ? `${quantity.quantity.toLocaleString('en-US')} × ${unit}` : 'Not worked out'}{' '}
              <span className="muted">({quantity.explanation})</span>
            </>
          )}
        </dd>
        <dt>Price</dt>
        <dd>
          {q?.price != null ? `${formatEuro(q.price)} / ${unit}` : 'unknown'}
          {q?.comparison_price != null && q.comparison_unit && (
            <span className="muted">
              {' '}
              ({formatEuro(q.comparison_price)} / {q.comparison_unit})
            </span>
          )}
          {line.line_total_cents !== null && <> · line total {formatCents(line.line_total_cents)}</>}
        </dd>
        {(q?.available_date || q?.order_cutoff) && (
          <>
            <dt>Delivery</dt>
            <dd>
              {q.available_date && <>arrives {formatDay(q.available_date.slice(0, 10))}</>}
              {q.available_date && q.order_cutoff && ' · '}
              {q.order_cutoff && <>order by {formatDateTime(q.order_cutoff)}</>}
            </dd>
          </>
        )}
        {q?.quantity_known && q.available_amount !== null && (
          <>
            <dt>Stock</dt>
            <dd>{stockText(q.available_amount)}</dd>
          </>
        )}
        {line.facts?.delivery_reliability != null && (
          <>
            <dt>On time</dt>
            <dd>{percent(line.facts.delivery_reliability)}</dd>
          </>
        )}
        {line.facts?.carbon_kg_per_kg != null && (
          <>
            <dt>CO₂</dt>
            <dd>{line.facts.carbon_kg_per_kg.toLocaleString('en-US')} kg CO₂e per kg</dd>
          </>
        )}
        {line.facts?.origin && (
          <>
            <dt>Origin</dt>
            <dd>{originLabel(line.facts.origin)}</dd>
          </>
        )}
      </dl>
      {((q?.flags.length ?? 0) > 0 || quantity?.needs_confirmation) && (
        <ul className="warnings">
          {q?.flags.map((f) => (
            <li key={f}>{flagLabel(f)}</li>
          ))}
          {quantity?.needs_confirmation && <li>Quantity needs your confirmation</li>}
        </ul>
      )}
    </li>
  )
}

const percent = (x: number) => `${Math.round(x * 100)} %`
const originLabel = (o: string) => (o.toLowerCase() === 'fi' ? '🇫🇮 Finland' : o.toUpperCase())

// Gemini Decisions API: how sure it is that this product is what the buyer asked for. Tap/hover for the reason.
function Confidence({ value, reason }: { value: number | null; reason: string | null }) {
  if (value === null) return null
  const low = value < 0.8
  const label = (
    <>
      Gemini confidence {formatConfidence(value)}
      {low && <> · Gemini isn’t sure this is what you asked for</>}
    </>
  )
  if (!reason) return <p className={`confidence${low ? ' low' : ''}`}>{label}</p>
  return (
    <details className={`confidence${low ? ' low' : ''}`}>
      <summary title={reason}>{label}</summary>
      <p>{reason}</p>
    </details>
  )
}

const TIER_LABEL: Record<string, string> = { best: 'Best', better: 'Better', good: 'Good' }

// Up to 3 allergen-safe substitutes per refused line, best first (the backend's order is kept).
function Substitutes({ subs, nameOf }: { subs: Substitute[]; nameOf: (id: string) => string }) {
  const groups = [...new Set(subs.map((s) => s.replaces))]
  return (
    <>
      {groups.map((id) => (
        <div key={id} className="subs">
          <h3>Instead of {nameOf(id)}</h3>
          <ul>
            {subs
              .filter((s) => s.replaces === id)
              .map((s) => (
                <li key={s.product_id}>
                  <p>
                    <span className={`badge tier-${s.tier}`}>{TIER_LABEL[s.tier] ?? s.tier}</span> <strong>{s.name}</strong>{' '}
                    <span className="muted">#{s.product_id}</span>
                  </p>
                  <p>{s.why_safe}</p>
                  <p className="muted">
                    {s.unit_price_cents !== null ? `${formatCents(s.unit_price_cents)} / ${s.unit ?? 'unit'}` : 'price unknown'}
                    {' · '}
                    {s.reliability !== null ? `on time ${percent(s.reliability)}` : 'no delivery record'}
                    {' · '}
                    {s.available !== null ? stockText(s.available) : 'stock unknown'}
                    {s.origin && <> · {originLabel(s.origin)}</>}
                  </p>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </>
  )
}

function SplitProposal({ alt, busy, onUse }: { alt: AlternativeOrder; busy: boolean; onUse: () => void }) {
  return (
    <div className="subs">
      <h3>Split order proposal</h3>
      <p>{alt.summary}</p>
      <ul>
        {alt.lines.map((l) => (
          <li key={l.product_id}>
            {l.quantity?.toLocaleString('en-US')} × {l.unit ?? 'units'} {l.name}
            {l.line_total_cents !== null && <span className="muted"> · {formatCents(l.line_total_cents)}</span>}
            {l.replaces && <span className="muted"> · substitute</span>}
          </li>
        ))}
      </ul>
      <p>
        Total <strong>{formatCents(alt.total_cents)}</strong> <span className="muted">(net of VAT)</span>
      </p>
      <div className="actions">
        <button type="button" onClick={onUse} disabled={busy}>
          {busy ? 'Placing…' : 'Use this order'}
        </button>
      </div>
    </div>
  )
}

function DecisionCard({ run, requestedDate, onAction, onBusy, onAnnounce }: Props) {
  const [busy, setBusy] = useState<'approve' | 'reject' | 'place' | null>(null)
  const [result, setResult] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signOff, setSignOff] = useState<string | null>(null) // 'Approved by Chef Aino' after a human decided
  const heading = useRef<HTMLHeadingElement>(null)

  // The front door's verdict wins over the agent's own: it re-checks with fresh quotes.
  const order = result ?? run.order
  const decision = order?.decision ?? run.decision
  const [tone, title] = order ? resultView(order.status) : outcomeView(run.decision.outcome)
  const awaitingApproval = order?.status === 'pending_approval' && order.order_id !== null

  useEffect(() => {
    onAnnounce(title)
    heading.current?.focus()
  }, [title, result, onAnnounce])

  async function act(action: 'approve' | 'reject' | 'place') {
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
      }
      onAction()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
      onBusy(false)
    }
  }

  const canDecide = MOCK || Boolean(getKeys().approverKey)
  const subs = order?.substitutes ?? []
  const nameOf = (id: string) =>
    order?.lines.find((l) => l.product_id === id)?.name ??
    run.lines.find((l) => l.product.id === id)?.product.name_en ??
    id

  return (
    <div className={`card decision ${tone}`}>
      <h2 ref={heading} tabIndex={-1}>
        {title}
      </h2>
      {run.decision.confidence != null && <p className="muted">Gemini confidence {formatConfidence(run.decision.confidence)}</p>}
      {order?.order_id && (tone === 'good' || awaitingApproval) && (
        <p>
          Order <code>{order.order_id}</code>
          {order.total_cents > 0 && <> · {formatCents(order.total_cents)} <span className="muted">(net of VAT)</span></>}
        </p>
      )}
      {signOff && <p>{signOff}</p>}
      {decision.reasons.length > 0 && (
        <>
          <h3>{signOff ? 'Original reason' : 'Why'}</h3>
          <ul className={signOff ? 'muted' : undefined}>
            {decision.reasons.map((r, i) => (
              <li key={i}>
                {r.message}
                {r.suggested_fix && <span className="muted"> {r.suggested_fix}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {subs.length > 0 && <Substitutes subs={subs} nameOf={nameOf} />}
      {order?.alternative_order && (
        <SplitProposal alt={order.alternative_order} busy={busy === 'place'} onUse={() => act('place')} />
      )}
      {subs.length === 0 && decision.alternatives.length > 0 && (
        <>
          <h3>Alternatives</h3>
          <ul>
            {decision.alternatives.map((a, i) => (
              <li key={i}>
                {a.summary} <span className="muted">#{a.product_id}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {awaitingApproval && (
        <>
          {!canDecide && <p className="muted">Enter the approver key in Keys to approve.</p>}
          <div className="actions">
            <button type="button" onClick={() => act('approve')} disabled={busy !== null || !canDecide}>
              {busy === 'approve' ? 'Approving…' : 'Approve order'}
            </button>
            <button type="button" className="secondary" onClick={() => act('reject')} disabled={busy !== null || !canDecide}>
              {busy === 'reject' ? 'Rejecting…' : 'Reject'}
            </button>
          </div>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
