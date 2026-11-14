import { useEffect, useRef, useState } from 'react'
import { decideOrder, getKeys, getOrder, MOCK, placeOrder } from './api'
import { CONFIDENT_AT, confidenceSentence, headline, STATUS, unitName } from './copy'
import {
  errorText, flagLabel, formatCents, formatConfidence, formatDateTime, formatDay, formatEuro, outcomeView, resultView, stockText,
} from './format'
import type { AgentRun, AlternativeOrder, Line, OrderResponse, Substitute } from './types'

type Props = {
  run: AgentRun
  requestedDate: string // the delivery date the run was for; a split order is placed for the same date
  onAction: () => void // an approve/reject/place finished (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (headline: string) => void
}
type Action = 'approve' | 'reject' | 'place'

const region = new Intl.DisplayNames(['en'], { type: 'region' })
const country = (code: string) => {
  try {
    return region.of(code.toUpperCase()) ?? code.toUpperCase()
  } catch {
    return code.toUpperCase()
  }
}
const productName = (l: Line) => l.product.name_en ?? l.product.name_fi ?? l.product.id
const count = (n: number) => n.toLocaleString('en-US')

export function RunResult({ run, requestedDate, onAction, onBusy, onAnnounce }: Props) {
  const [busy, setBusy] = useState<Action | null>(null)
  const [result, setResult] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signOff, setSignOff] = useState<string | null>(null) // 'Approved by Chef Aino' after a human decided
  const heading = useRef<HTMLHeadingElement>(null)

  // The front door's verdict wins over the agent's own: it re-checks with fresh quotes.
  const order = result ?? run.order
  const decision = order?.decision ?? run.decision
  const statusKey = order ? order.status : run.decision.outcome
  const [tone] = order ? resultView(order.status) : outcomeView(run.decision.outcome)
  const status = STATUS[statusKey] ?? statusKey
  const lead = signOff ? null : (decision.reasons[0] ?? null)
  const awaitingApproval = order?.status === 'pending_approval' && order.order_id !== null
  const canDecide = MOCK || Boolean(getKeys().approverKey)

  const text = signOff
    ? `${signOff}.`
    : order?.status === 'confirmed'
      ? `Ordered for ${formatDay(requestedDate)}.`
      : order?.status === 'rejected'
        ? 'Rejected. Nothing was ordered.'
        : lead
          ? headline(lead)
          : status

  const chosen = run.lines.filter((l) => l.chosen)
  const others = run.lines.filter((l) => !l.chosen)
  const total = order?.total_cents || chosen.reduce((a, l) => a + (l.line_total_cents ?? 0), 0)
  const what =
    chosen.length === 1
      ? `${chosen[0].quantity?.quantity != null ? `${count(chosen[0].quantity.quantity)} × ` : ''}${productName(chosen[0])}`
      : chosen.length > 1
        ? `${chosen.length} products`
        : null
  const confidence = chosen.length === 1 && chosen[0].confidence != null ? chosen[0].confidence : run.decision.confidence
  // When Gemini is unsure, its own reason says more than a generic sentence ("a milk drink, not milk").
  const unsureWhy = chosen.length === 1 ? chosen[0].confidence_reason : null

  useEffect(() => {
    onAnnounce(`${status}. ${text}`)
    heading.current?.focus() // also brings the answer into view on a phone
  }, [status, text, result, onAnnounce])

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

  const subs = order?.substitutes ?? []
  const otherReasons = signOff ? decision.reasons : decision.reasons.slice(1)
  const query = run.request.items.length === 1 ? run.request.items[0].query : null

  return (
    <>
      <section className="answer" aria-label="Agent result">
        <p className={`status ${tone}`}>{status}</p>
        <h2 ref={heading} tabIndex={-1} className="answer-text">
          {text}
        </h2>
        {(what || total > 0) && (
          <p className="answer-sub">
            {what && <>{what}. </>}
            {total > 0 && (
              <>
                <strong>{formatCents(total)}</strong> before VAT.
              </>
            )}
            {!awaitingApproval && lead?.suggested_fix && <> {lead.suggested_fix}</>}
          </p>
        )}
        {confidence != null && (
          <p className={`sure num${confidence < CONFIDENT_AT ? ' unsure' : ''}`}>
            {confidence < CONFIDENT_AT && unsureWhy ? unsureWhy.replace(/\.$/, '') : confidenceSentence(confidence)} ·{' '}
            {formatConfidence(confidence)}
          </p>
        )}
        {awaitingApproval && (
          <div className="decide">
            <button type="button" className="btn" onClick={() => act('approve')} disabled={busy !== null || !canDecide}>
              {busy === 'approve' ? 'Approving…' : `Approve ${formatCents(total)}`}
            </button>
            <button type="button" className="btn plain bad" onClick={() => act('reject')} disabled={busy !== null || !canDecide}>
              {busy === 'reject' ? 'Rejecting…' : 'Reject'}
            </button>
            {!canDecide && <p className="hint note">Add your approver key under Keys to approve.</p>}
          </div>
        )}
        {error && (
          <div className="problem" role="alert">
            <strong>That didn’t go through.</strong>
            {error}
          </div>
        )}
      </section>

      {order?.alternative_order && (
        <SplitProposal alt={order.alternative_order} busy={busy === 'place'} disabled={busy !== null} onUse={() => act('place')} />
      )}
      {subs.length > 0 && <Substitutes subs={subs} />}

      <div className="more">
        {chosen.map((l) => (
          <details key={l.product.id}>
            <summary>{chosen.length === 1 && query ? `Why this ${query}` : `Why ${productName(l)}`}</summary>
            <WhyThis line={l} />
          </details>
        ))}
        {otherReasons.length > 0 && (
          <details>
            <summary>{signOff ? 'Why it needed your OK' : `Also worth knowing (${otherReasons.length})`}</summary>
            <ul className="more-body">
              {otherReasons.map((r, i) => (
                <li key={i}>
                  <p>{r.message}</p>
                  {r.suggested_fix && <p className="quiet small">{r.suggested_fix}</p>}
                </li>
              ))}
            </ul>
          </details>
        )}
        {others.length > 0 && (
          <details>
            <summary>Other options ({others.length})</summary>
            <ul className="more-body">
              {others.map((l) => (
                <OtherOption key={l.product.id} line={l} />
              ))}
            </ul>
          </details>
        )}
        <details>
          <summary>What the agent understood</summary>
          <div className="more-body">
            <p>{run.request.summary}</p>
            {run.request.items.length > 1 && (
              <ul className="quiet small">
                {run.request.items.map((it, i) => (
                  <li key={i}>{[it.amount, it.unit, it.query].filter((x) => x !== null).join(' ')}</li>
                ))}
              </ul>
            )}
          </div>
        </details>
      </div>
    </>
  )
}

function availability(line: Line): [string, string] {
  const q = line.quote
  if (!q) return ['bad', 'Valio didn’t quote this.']
  const blocking = q.flags.filter((f) => f !== 'quantity_unknown')
  if (blocking.length) return ['bad', `${blocking.map(flagLabel).join('. ')}.`]
  const stock = q.flags.includes('quantity_unknown') || q.available_amount === null ? 'Stock unknown' : stockText(q.available_amount)
  const when = [q.order_cutoff && `order by ${formatDateTime(q.order_cutoff)}`, q.available_date && `arrives ${formatDay(q.available_date.slice(0, 10))}`]
    .filter(Boolean)
    .join(', ')
  return [q.flags.includes('quantity_unknown') ? 'warn' : '', `${stock}${when ? `, ${when}` : ''}.`]
}

function facts(line: Line): string | null {
  const f = line.facts
  const rel = f ? f.delivery_reliability : line.product.delivery_reliability
  const co2 = f ? f.carbon_kg_per_kg : line.product.carbon_kg_per_kg
  const parts = [
    rel != null && `On time for ${Math.round(rel * 100)}% of deliveries.`,
    f?.origin && `From ${country(f.origin)}.`,
    co2 != null && `${co2.toLocaleString('en-US')} kg CO₂e per kg.`,
  ].filter(Boolean)
  return parts.length ? parts.join(' ') : null
}

function WhyThis({ line }: { line: Line }) {
  const [, avail] = availability(line)
  const q = line.quote
  const f = facts(line)
  return (
    <div className="more-body">
      {line.why && <p>{line.why}</p>}
      {line.confidence_reason && <p className="quiet">{line.confidence_reason}</p>}
      <p className="quiet">
        {avail}
        {q?.price != null && ` ${formatEuro(q.price)} per ${unitName(line.quantity?.sales_unit || line.product.sales_unit)}.`}
      </p>
      {f && <p className="quiet">{f}</p>}
      {line.quantity && <p className="quiet small">{line.quantity.explanation}</p>}
    </div>
  )
}

function OtherOption({ line }: { line: Line }) {
  const [tone, avail] = availability(line)
  const unsure = line.confidence != null && line.confidence < CONFIDENT_AT
  const why =
    tone === 'bad'
      ? avail
      : unsure
        ? `${(line.confidence_reason ?? confidenceSentence(line.confidence!)).replace(/\.$/, '')} · ${formatConfidence(line.confidence!)}`
        : line.why || avail
  return (
    <li className="option">
      <div>
        <p>{productName(line)}</p>
        <p className={`option-why ${tone === 'bad' ? 'bad' : unsure ? 'warn' : ''}`}>{why}</p>
      </div>
      <p className="option-side quiet">{line.line_total_cents !== null ? formatCents(line.line_total_cents) : '—'}</p>
    </li>
  )
}

const RANK: Record<string, string> = { best: 'Best match', better: 'Good match', good: 'Works if needed' }

// Allergen-safe substitutes for a line Valio can't deliver, best first (the backend's order is kept).
function Substitutes({ subs }: { subs: Substitute[] }) {
  return (
    <section className="instead" aria-labelledby="subs-title">
      <h2 className="title" id="subs-title">
        Valio has these instead
      </h2>
      <ul>
        {subs.map((s) => (
          <li key={`${s.replaces}-${s.product_id}`} className="alt">
            <div>
              <p className="alt-rank">{RANK[s.tier] ?? s.tier}</p>
              <p>{s.name}</p>
              <p className="quiet small">{s.why_safe}</p>
            </div>
            <div className="alt-side">
              <p>{s.unit_price_cents !== null ? formatCents(s.unit_price_cents) : '—'}</p>
              <p className="quiet small">per {unitName(s.unit)}</p>
              <p className="quiet small">
                {s.reliability !== null
                  ? `${Math.round(s.reliability * 100)}% on time`
                  : s.available !== null
                    ? stockText(s.available)
                    : 'Stock unknown'}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function SplitProposal({ alt, busy, disabled, onUse }: { alt: AlternativeOrder; busy: boolean; disabled: boolean; onUse: () => void }) {
  return (
    <section className="instead" aria-labelledby="split-title">
      <h2 className="title" id="split-title">
        Valio can cover it with {alt.lines.length} products
      </h2>
      <div>
        {alt.lines.map((l) => (
          <div key={l.product_id} className="split-row">
            <span>
              {l.name}
              {l.replaces && <span className="quiet"> (substitute)</span>}
            </span>
            <span className="qty r">
              {l.quantity != null ? count(l.quantity) : '—'} × {unitName(l.unit)}
            </span>
            <span className="r">{l.line_total_cents !== null ? formatCents(l.line_total_cents) : '—'}</span>
          </div>
        ))}
        <div className="split-total">
          <span>
            <strong>{formatCents(alt.total_cents)}</strong> <span className="quiet">before VAT</span>
          </span>
          <button type="button" className="btn" onClick={onUse} disabled={disabled}>
            {busy ? 'Placing…' : 'Use this order'}
          </button>
        </div>
      </div>
    </section>
  )
}
