import { useEffect, useRef, useState } from 'react'
import { decideOrder, getKeys, MOCK } from './api'
import { errorText, flagLabel, formatCents, formatDateTime, formatDay, formatEuro, outcomeView, resultView } from './format'
import type { AgentRun, Line, OrderResponse } from './types'

type Props = {
  run: AgentRun
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
            <dt>In stock</dt>
            <dd>{q.available_amount.toLocaleString('en-US')}</dd>
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

function DecisionCard({ run, onAction, onBusy, onAnnounce }: Omit<Props, 'run'> & { run: AgentRun }) {
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [result, setResult] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
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

  async function act(action: 'approve' | 'reject') {
    if (!order?.order_id) return
    setBusy(action)
    onBusy(true)
    setError(null)
    try {
      setResult(await decideOrder(order.order_id, action))
      onAction()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
      onBusy(false)
    }
  }

  const canDecide = MOCK || Boolean(getKeys().approverKey)

  return (
    <div className={`card decision ${tone}`}>
      <h2 ref={heading} tabIndex={-1}>
        {title}
      </h2>
      {order?.order_id && (tone === 'good' || awaitingApproval) && (
        <p>
          Order <code>{order.order_id}</code>
          {order.total_cents > 0 && <> · {formatCents(order.total_cents)} <span className="muted">(net of VAT)</span></>}
        </p>
      )}
      {decision.reasons.length > 0 && (
        <>
          <h3>Why</h3>
          <ul>
            {decision.reasons.map((r, i) => (
              <li key={i}>
                {r.message}
                {r.suggested_fix && <span className="muted"> {r.suggested_fix}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {decision.alternatives.length > 0 && (
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
