import { useState } from 'react'
import { decideOrder } from './api'
import { errorText, flagLabel, formatCents, formatDateTime, formatDay, formatEuro } from './format'
import type { AgentRun, ApprovalResult, Decision, Line } from './types'

export function RunResult({ run, onAction }: { run: AgentRun; onAction: () => void }) {
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
              {it.amount} {it.unit} {it.query}
              {it.claims.length > 0 && <span className="muted"> · {it.claims.map(humanize).join(', ')}</span>}
              {it.exclude_allergens.length > 0 && <span className="muted"> · without {it.exclude_allergens.join(', ')}</span>}
            </li>
          ))}
        </ul>
      </div>

      <DecisionCard run={run} onAction={onAction} />

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
  return (
    <li className="line">
      <p className="line-name">
        <strong>{p.name_en ?? p.name_fi ?? p.id}</strong> <span className="muted">#{p.id}</span>
      </p>
      <p>{line.why}</p>
      <dl>
        <dt>Quantity</dt>
        <dd>
          {quantity.sales_units} × {p.sales_unit} <span className="muted">({quantity.explanation})</span>
        </dd>
        <dt>Price</dt>
        <dd>
          {q.price !== null ? `${formatEuro(q.price)} / ${p.sales_unit}` : 'unknown'}
          {q.comparison_price !== null && q.comparison_unit && (
            <span className="muted">
              {' '}
              ({formatEuro(q.comparison_price)} / {q.comparison_unit})
            </span>
          )}
          {line.line_total_cents !== null && <> · line total {formatCents(line.line_total_cents)}</>}
        </dd>
        {(q.available_date || q.order_cutoff) && (
          <>
            <dt>Delivery</dt>
            <dd>
              {q.available_date && <>arrives {formatDay(q.available_date)}</>}
              {q.available_date && q.order_cutoff && ' · '}
              {q.order_cutoff && <>order by {formatDateTime(q.order_cutoff)}</>}
            </dd>
          </>
        )}
        {q.quantity_known && q.available_amount !== null && (
          <>
            <dt>In stock</dt>
            <dd>{q.available_amount.toLocaleString('en-US')}</dd>
          </>
        )}
      </dl>
      {(q.flags.length > 0 || quantity.needs_confirmation) && (
        <ul className="warnings">
          {q.flags.map((f) => (
            <li key={f}>{flagLabel(f)}</li>
          ))}
          {quantity.needs_confirmation && <li>Quantity needs your confirmation</li>}
        </ul>
      )}
    </li>
  )
}

type Tone = 'good' | 'warn' | 'bad' | 'neutral'
const OUTCOME_VIEW: Record<Decision['outcome'], [Tone, string]> = {
  ORDERED: ['good', 'Ordered by the agent'],
  NEEDS_APPROVAL: ['warn', 'Needs your approval'],
  REFUSED: ['bad', 'Not ordered'],
}
const RESULT_VIEW: Record<ApprovalResult['status'], [Tone, string]> = {
  ORDERED: ['good', 'Approved and ordered'],
  REJECTED: ['neutral', 'Rejected: nothing was ordered'],
  REFUSED: ['bad', 'Refused at Valio’s front door'],
}

function DecisionCard({ run, onAction }: { run: AgentRun; onAction: () => void }) {
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [result, setResult] = useState<ApprovalResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function act(action: 'approve' | 'reject') {
    if (!run.order) return
    setBusy(action)
    setError(null)
    try {
      setResult(await decideOrder(run.order.order_id, action))
      onAction()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const decision: Decision = result?.decision ?? run.decision
  const orderId = result?.order_id ?? run.order?.order_id
  const [tone, title] = result ? RESULT_VIEW[result.status] : OUTCOME_VIEW[run.decision.outcome]
  const awaitingApproval = !result && run.decision.outcome === 'NEEDS_APPROVAL' && run.order !== null

  return (
    <div className={`card decision ${tone}`} aria-live="polite">
      <h2>{title}</h2>
      {orderId && (tone === 'good' || awaitingApproval) && (
        <p>
          Order <code>{orderId}</code>
        </p>
      )}
      {decision.reasons.length > 0 && (
        <>
          <h3>Why</h3>
          <ul>
            {decision.reasons.map((r, i) => (
              <li key={i}>{r.text}</li>
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
                {a.text} <span className="muted">#{a.product_id}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {awaitingApproval && (
        <div className="actions">
          <button type="button" onClick={() => act('approve')} disabled={busy !== null}>
            {busy === 'approve' ? 'Approving…' : 'Approve order'}
          </button>
          <button type="button" className="secondary" onClick={() => act('reject')} disabled={busy !== null}>
            {busy === 'reject' ? 'Rejecting…' : 'Reject'}
          </button>
        </div>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
