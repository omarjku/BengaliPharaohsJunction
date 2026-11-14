import { useEffect, useRef, useState, type RefObject } from 'react'
import { decideOrder, getKeys, getOrder, MOCK, placeOrder } from './api'
import { amountOf, CONFIDENCE_MEANS, CONFIDENT_AT, headline, humanize, matched, tidyName, unitName } from './copy'
import { errorText, flagLabel, formatCents, formatDateTime, formatDay, formatEuro, stockText, type Tone } from './format'
import type { AgentRun, AlternativeOrder, Line, OrderInput, OrderResponse, Substitute } from './types'

type Props = {
  run: AgentRun
  requestedDate: string // the delivery date the run was for; any follow-up order is placed for the same date
  onAction: () => void // something was decided or ordered (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (headline: string) => void
  onRetry?: () => void // "Not this one": back to the request field
}
type Busy = 'approve' | 'reject' | 'place' | null

const region = new Intl.DisplayNames(['en'], { type: 'region' })
const country = (code: string) => {
  try {
    return region.of(code.toUpperCase()) ?? code.toUpperCase()
  } catch {
    return code.toUpperCase()
  }
}
const productName = (l: Line) => tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Helsinki' })
const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' })
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date())

// "Arrives Monday, in 2 days."
function arrives(ymd: string): string {
  const days = Math.round((Date.parse(`${ymd}T00:00:00Z`) - Date.parse(`${today()}T00:00:00Z`)) / 86_400_000)
  const day = weekday.format(new Date(`${ymd}T00:00:00Z`))
  return days === 0 ? 'Arrives today.' : days === 1 ? 'Arrives tomorrow.' : days > 1 && days < 8 ? `Arrives ${day}, in ${days} days.` : `Arrives ${formatDay(ymd)}.`
}

// Shown once the element has been on screen: the phone's action bar waits until the reasons have been seen.
function useSeen<T extends Element>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setSeen(true), { threshold: 1 })
    io.observe(el)
    return () => io.disconnect()
  }, [seen])
  return [ref, seen]
}

const orderable = (l: Line) => l.quote != null && l.quote.orderable && l.quantity?.quantity != null && l.line_total_cents != null
const lineOrder = (l: Line) => ({ product_id: l.product.id, quantity: l.quantity!.quantity! })

export function RunResult({ run, requestedDate, onAction, onBusy, onAnnounce, onRetry }: Props) {
  const [busy, setBusy] = useState<Busy>(null)
  const [result, setResult] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signOff, setSignOff] = useState<string | null>(null) // "Chef Aino approved · 04:52"
  const [justDone, setJustDone] = useState(false) // Approve briefly turns into "Ordered ✓"
  const heading = useRef<HTMLHeadingElement>(null)
  const [reasonsRef, reasonsSeen] = useSeen<HTMLParagraphElement>()

  // The front door's verdict wins over the agent's own: it re-checks with fresh quotes.
  const order = result ?? run.order
  const decision = order?.decision ?? run.decision
  const split = order?.status === 'refused' ? (order.alternative_order ?? null) : null
  const subs = order?.substitutes ?? []
  const chosen = run.lines.filter((l) => l.chosen)
  const others = run.lines.filter((l) => !l.chosen)
  const guess = !order && run.decision.outcome === 'ASK_HUMAN' && chosen.length === 1 && orderable(chosen[0]) ? chosen[0] : null

  // Honest status: red only when it's final; amber when it's the chef's call; green when it's ordered.
  const [tone, status]: [Tone, string] = order
    ? order.status === 'confirmed'
      ? ['good', 'Ordered']
      : order.status === 'pending_approval'
        ? ['warn', 'Your call']
        : order.status === 'rejected'
          ? ['neutral', 'Rejected']
          : order.status === 'refused' && (split || subs.length)
            ? ['warn', 'Your call']
            : order.status === 'refused'
              ? ['bad', 'Not ordered']
              : ['neutral', order.status]
    : run.decision.outcome === 'DECLINE'
      ? ['bad', 'Not ordered']
      : run.decision.outcome === 'ASK_HUMAN'
        ? ['warn', 'Your call']
        : ['neutral', 'Sent to Valio']

  const lead = decision.reasons[0] ?? null
  const text =
    order?.status === 'confirmed'
      ? `Ordered for ${formatDay(requestedDate)}.`
      : order?.status === 'rejected'
        ? 'Rejected. Nothing was ordered.'
        : split
          ? splitHeadline(split)
          : lead
            ? headline(lead)
            : status

  const total = order?.total_cents || chosen.reduce((a, l) => a + (l.line_total_cents ?? 0), 0)
  const what = split
    ? null // the headline already says what the split is
    : chosen.length === 1
      ? `${chosen[0].quantity?.quantity != null ? `${amountOf(chosen[0].quantity.quantity, chosen[0].quantity.sales_unit)} of ` : ''}${productName(chosen[0])}`
      : chosen.length > 1
        ? `${chosen.length} products`
        : null
  const confidence = chosen.length === 1 && chosen[0].confidence != null ? chosen[0].confidence : run.decision.confidence
  const awaitingApproval = order?.status === 'pending_approval' && order.order_id !== null
  const canDecide = MOCK || Boolean(getKeys().approverKey)

  useEffect(() => {
    onAnnounce(`${status}. ${text}`)
    heading.current?.focus() // also brings the answer into view on a phone
  }, [status, text, result, onAnnounce])

  async function run_(kind: Busy, go: () => Promise<OrderResponse>) {
    setBusy(kind)
    onBusy(true)
    setError(null)
    try {
      const res = await go()
      setResult(res)
      if (kind === 'approve' || kind === 'reject') {
        const who = await getOrder(res.order_id ?? order!.order_id!).then((o) => o.signed_off_by, () => null) // a nicety
        setSignOff(`${who ?? 'You'} ${kind === 'approve' ? 'approved' : 'rejected'} · ${clock.format(new Date())}`)
        if (kind === 'approve' && res.status === 'confirmed') {
          setJustDone(true)
          setTimeout(() => setJustDone(false), 1400)
        }
      } else setSignOff(null)
      onAction()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
      onBusy(false)
    }
  }
  const decide = (action: 'approve' | 'reject') => run_(action, () => decideOrder(order!.order_id!, action))
  const place = (lines: OrderInput['lines']) => run_('place', () => placeOrder({ requested_date: requestedDate, lines }))

  const otherReasons = decision.reasons.slice(1)
  const query = run.request.items.length === 1 ? run.request.items[0].query : null

  return (
    <>
      <section className="answer" aria-label="Agent result">
        <p className={`status ${tone}`}>{status}</p>
        <h2 ref={heading} tabIndex={-1} className="answer-text num">
          {text}
        </h2>
        {signOff && <p className="signoff">{signOff}</p>}
        <p className="answer-sub" ref={reasonsRef}>
          {what && <>{what}. </>}
          {total > 0 && (
            <>
              <strong>{formatCents(split ? split.total_cents : total)}</strong> excl. VAT{split ? ' for both' : ''}.
            </>
          )}
          {order?.status === 'confirmed' && <> {arrives(requestedDate)}</>}
          {!awaitingApproval && !split && !guess && order?.status !== 'confirmed' && order?.status !== 'rejected' && lead?.suggested_fix && (
            <> {lead.suggested_fix}</>
          )}
        </p>
        {confidence != null && (
          <p className={`sure num${confidence < CONFIDENT_AT ? ' unsure' : ''}`}>
            {matched(confidence)}
            {confidence < CONFIDENT_AT && chosen[0]?.confidence_reason && <span className="quiet">. {chosen[0].confidence_reason}</span>}
          </p>
        )}

        {(awaitingApproval || justDone) && (
          <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
            {justDone ? (
              <button type="button" className="btn done" disabled>
                Ordered ✓
              </button>
            ) : (
              <>
                <button type="button" className="btn" onClick={() => decide('approve')} disabled={busy !== null || !canDecide}>
                  {busy === 'approve' ? 'Approving…' : `Approve · ${formatCents(total)}`}
                </button>
                <button type="button" className="btn plain" onClick={() => decide('reject')} disabled={busy !== null || !canDecide}>
                  {busy === 'reject' ? 'Rejecting…' : 'Reject'}
                </button>
                {!canDecide && <p className="hint note">Add your approver key under Keys to approve.</p>}
              </>
            )}
          </div>
        )}
        {split && (
          <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
            <button type="button" className="btn" onClick={() => place(split.lines.map((l) => ({ product_id: l.product_id, quantity: l.quantity ?? 0 })))} disabled={busy !== null}>
              {busy === 'place' ? 'Ordering…' : `${split.lines.length === 2 ? 'Order both' : 'Order these'} · ${formatCents(split.total_cents)}`}
            </button>
          </div>
        )}
        {(guess || (!order && run.decision.outcome === 'ASK_HUMAN')) && (
          <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
            {guess && (
              <button type="button" className="btn" onClick={() => place([lineOrder(guess)])} disabled={busy !== null}>
                {busy === 'place' ? 'Ordering…' : `Order it · ${formatCents(guess.line_total_cents!)}`}
              </button>
            )}
            {onRetry && (
              <button type="button" className="btn plain" onClick={onRetry} disabled={busy !== null}>
                Not this one
              </button>
            )}
          </div>
        )}
        {error && (
          <div className="problem" role="alert">
            <strong>That didn’t go through.</strong>
            {error}
          </div>
        )}
      </section>

      {split && <SplitRows alt={split} />}
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
                  <p>{humanize(r.message)}</p>
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
                <OtherOption key={l.product.id} line={l} onOrder={!order && run.decision.outcome !== 'DECLINE' && orderable(l) ? () => place([lineOrder(l)]) : null} busy={busy !== null} />
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

// "Valio has 640. Top up with 360 organic?"
function splitHeadline(alt: AlternativeOrder): string {
  const [have, rest] = alt.lines
  if (!have || !rest || have.quantity == null || rest.quantity == null) return 'Valio can cover it with a substitute.'
  const a = tidyName(have.name), b = tidyName(rest.name)
  const extra = b.startsWith(a) ? b.slice(a.length).replace(/^[,\s]+/, '') : b
  return `Valio has ${have.quantity.toLocaleString('en-US')}. Top up with ${rest.quantity.toLocaleString('en-US')} ${extra}?`
}

function availability(line: Line): [string, string] {
  const q = line.quote
  if (!q) return ['bad', 'Valio didn’t quote this.']
  const blocking = q.flags.filter((f) => f !== 'quantity_unknown')
  if (blocking.length) return ['bad', `${blocking.map(flagLabel).join('. ')}.`]
  const stock = q.flags.includes('quantity_unknown') || q.available_amount === null ? 'Stock not confirmed' : stockText(q.available_amount)
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
      {line.why && <p>{humanize(line.why)}</p>}
      {line.confidence != null && (
        <p className="quiet num">
          {matched(line.confidence)}.{line.confidence_reason && ` ${line.confidence_reason}`}
        </p>
      )}
      <p className="quiet">
        {avail}
        {q?.price != null && ` ${formatEuro(q.price)} per ${unitName(line.quantity?.sales_unit || line.product.sales_unit)}.`}
      </p>
      {f && <p className="quiet">{f}</p>}
      {line.quantity && <p className="quiet small">{line.quantity.explanation}</p>}
      {line.confidence != null && <p className="faint tiny">{CONFIDENCE_MEANS}</p>}
    </div>
  )
}

function OtherOption({ line, onOrder, busy }: { line: Line; onOrder: (() => void) | null; busy: boolean }) {
  const [tone, avail] = availability(line)
  const unsure = line.confidence != null && line.confidence < CONFIDENT_AT
  const why = tone === 'bad' ? avail : line.confidence != null ? matched(line.confidence) : line.why || avail
  return (
    <li className="option">
      <div>
        <p>{productName(line)}</p>
        <p className={`option-why num ${tone === 'bad' ? 'bad' : unsure ? 'warn' : ''}`}>{why}</p>
        {onOrder && (
          <button type="button" className="btn plain accent-text small-btn" onClick={onOrder} disabled={busy}>
            Order this instead
          </button>
        )}
      </div>
      <p className="option-side quiet">{line.line_total_cents !== null ? formatCents(line.line_total_cents) : '—'}</p>
    </li>
  )
}

const RANK: Record<string, string> = { best: 'Best match', better: 'Good match', good: 'Also works' }

// Allergen-safe substitutes for a line Valio can't deliver, best first (the backend's order is kept).
function Substitutes({ subs }: { subs: Substitute[] }) {
  return (
    <section className="instead" aria-labelledby="subs-title">
      <h2 className="title" id="subs-title">
        Other choices Valio has
      </h2>
      <ul>
        {subs.map((s) => (
          <li key={`${s.replaces}-${s.product_id}`} className="alt">
            <div>
              <p className="alt-rank">{RANK[s.tier] ?? s.tier}</p>
              <p>{tidyName(s.name)}</p>
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
                    : 'Stock not confirmed'}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function SplitRows({ alt }: { alt: AlternativeOrder }) {
  return (
    <section className="instead" aria-label="The split order">
      <div>
        {alt.lines.map((l) => (
          <div key={l.product_id} className="split-row">
            <span>
              {tidyName(l.name)}
              {l.replaces && <span className="quiet"> (substitute)</span>}
            </span>
            <span className="qty r">{l.quantity != null ? amountOf(l.quantity, l.unit) : '—'}</span>
            <span className="r">{l.line_total_cents !== null ? formatCents(l.line_total_cents) : '—'}</span>
          </div>
        ))}
        <div className="split-total">
          <span>
            <strong>{formatCents(alt.total_cents)}</strong> <span className="quiet">in total</span>
          </span>
        </div>
      </div>
    </section>
  )
}
