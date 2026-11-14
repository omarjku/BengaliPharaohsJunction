import { useEffect, useRef, useState, type FormEvent, type ReactNode, type RefObject } from 'react'
import { decideOrder, getKeys, getOrder, MOCK, placeOrder } from './api'
import { CONFIDENT_AT, tidyName } from './copy'
import { errorText, type Tone } from './format'
import { useCopy, type Copy } from './i18n'
import type { AgentRun, AlternativeOrder, Line, OrderInput, OrderResponse, Substitute } from './types'
import './RunResult.css'
import { Compare } from './Compare'

type Props = {
  run: AgentRun
  requestedDate: string // the delivery date the run was for; any follow-up order is placed for the same date
  onAction: () => void // something was decided or ordered (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (headline: string) => void
  onRetry?: () => void // "Not this one": back to the request field
  onHistory?: () => void // "See it in History", from the front-door line
  onAskFor?: (text: string) => void // a substitute in another pack size: ask the agent for it (it works out the amount)
  onPlain?: (need: string) => void // "Not gluten-free this time": ask again without the profile's dietary default
  after?: ReactNode // shown right under the answer (e.g. "Need it sooner?"), before the details
}
type Busy = 'approve' | 'reject' | 'place' | null
type Pick = { label: string; go: () => void }

const productName = (l: Line) => tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Helsinki' })
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date())

// "Arrives Monday, in 2 days."
function arrives(ymd: string, c: Copy): string {
  const days = Math.round((Date.parse(`${ymd}T00:00:00Z`) - Date.parse(`${today()}T00:00:00Z`)) / 86_400_000)
  return c.UI.result.arrives(days, c.weekday(ymd), c.day(ymd))
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

export function RunResult({ run, requestedDate, onAction, onBusy, onAnnounce, onRetry, onHistory, onAskFor, onPlain, after }: Props) {
  const [busy, setBusy] = useState<Busy>(null)
  const [placing, setPlacing] = useState<string | null>(null) // which option's button is ordering (its label says so)
  const errorRef = useRef<HTMLDivElement>(null)
  const [result, setResult] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signOff, setSignOff] = useState<string | null>(null) // "Chef Aino approved · 04:52"
  const [justDone, setJustDone] = useState(false) // Approve briefly turns into "Ordered ✓"
  const [selected, setSelected] = useState<string | null>(null) // the option card picked (default: the agent's pick)
  const [changing, setChanging] = useState(false) // "Change quantity" open
  const [amount, setAmount] = useState('')
  const [comparing, setComparing] = useState(false) // the compare view is open
  const heading = useRef<HTMLHeadingElement>(null)
  const [reasonsRef, reasonsSeen] = useSeen<HTMLParagraphElement>()
  const c = useCopy()
  const t = c.UI.result
  const st = c.UI.status

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
      ? ['good', st.ordered]
      : order.status === 'pending_approval'
        ? ['warn', st.yourCall]
        : order.status === 'rejected'
          ? ['neutral', st.rejected]
          : order.status === 'refused' && (split || subs.length)
            ? ['warn', st.yourCall]
            : order.status === 'refused'
              ? ['bad', st.notOrdered]
              : ['neutral', order.status]
    : run.decision.outcome === 'DECLINE'
      ? ['bad', st.notOrdered]
      : run.decision.outcome === 'ASK_HUMAN'
        ? ['warn', st.yourCall]
        : ['neutral', st.sent]

  const lead = decision.reasons[0] ?? null
  const text =
    order?.status === 'confirmed'
      ? t.orderedFor(c.day(requestedDate))
      : order?.status === 'rejected'
        ? t.rejected
        : split
          ? splitHeadline(split, c)
          : lead
            ? c.headline(lead)
            : status
  const [head, more] = splitLong(text, c)

  const total = order?.total_cents || chosen.reduce((a, l) => a + (l.line_total_cents ?? 0), 0)
  const what = split
    ? null // the headline already says what the split is
    : chosen.length === 1
      ? chosen[0].quantity?.quantity != null
        ? t.of(c.amountOf(chosen[0].quantity.quantity, chosen[0].quantity.sales_unit), productName(chosen[0]))
        : productName(chosen[0])
      : chosen.length > 1
        ? t.products(chosen.length)
        : null
  const confidence = chosen.length === 1 && chosen[0].confidence != null ? chosen[0].confidence : run.decision.confidence
  const awaitingApproval = order?.status === 'pending_approval' && order.order_id !== null
  const canDecide = MOCK || Boolean(getKeys().approverKey)

  useEffect(() => {
    onAnnounce(`${status}. ${head}`)
    heading.current?.focus() // also brings the answer into view on a phone
  }, [status, head, result, onAnnounce])

  async function run_(kind: Busy, go: () => Promise<OrderResponse>) {
    if (kind === 'place' && !MOCK && !getKeys().agentKey) {
      setPlacing(null)
      setError(t.keysFirst)
      requestAnimationFrame(() => errorRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
      return
    }
    setBusy(kind)
    onBusy(true)
    setError(null)
    try {
      const res = await go()
      setResult(res)
      if (kind === 'approve' || kind === 'reject') {
        const who = await getOrder(res.order_id ?? order!.order_id!).then((o) => o.signed_off_by, () => null) // a nicety
        setSignOff(t.signOff(who, kind === 'approve', clock.format(new Date())))
        if (kind === 'approve' && res.status === 'confirmed') {
          setJustDone(true)
          setTimeout(() => setJustDone(false), 1400)
        }
      } else setSignOff(null)
      onAction()
    } catch (err) {
      setError(errorText(err)) // the backend's own words (detail)
      requestAnimationFrame(() => errorRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
    } finally {
      setBusy(null)
      setPlacing(null)
      onBusy(false)
    }
  }
  const decide = (action: 'approve' | 'reject') => run_(action, () => decideOrder(order!.order_id!, action))
  const place = (lines: OrderInput['lines'], which = 'main') => {
    setPlacing(which)
    return run_('place', () => placeOrder({ requested_date: requestedDate, lines }))
  }
  // Another option can be chosen until something is ordered or waiting for the chef's OK.
  const canChoose = !order || order.status === 'refused' || order.status === 'rejected'
  // A substitute takes the refused line's amount when it comes in the same unit; otherwise the agent works it out.
  const pickSub = (s: Substitute): Pick | null => {
    if (!canChoose) return null
    const was = order?.lines.find((l) => l.product_id === s.replaces)
    if (was?.quantity != null && (was.unit ?? null) === (s.unit ?? null))
      return { label: t.orderInstead, go: () => place([{ product_id: s.product_id, quantity: was.quantity! }], s.product_id) }
    const asked = run.lines.find((l) => l.product.id === s.replaces)?.quantity?.requested
    return onAskFor ? { label: t.askFor, go: () => onAskFor(`${asked ? `${asked.amount} ${asked.unit} ` : ''}${tidyName(s.name)}`) } : null
  }

  // Calm notes stay out of "Also worth knowing": the Gemini line says the confidence, the front-door line the hand-off.
  // The profile's dietary default (INFO) gets its own line with an override, so it stays out of the list too.
  const profileNote = [...decision.reasons, ...run.decision.reasons].find((r) => r.code === 'PROFILE_DEFAULT' && r.severity === 'INFO')
  const need = profileNote?.message.split(',')[0].toLowerCase() ?? '' // "Gluten-free, because …" -> "gluten-free"
  const otherReasons = decision.reasons
    .slice(1)
    .filter((r) => r.code !== 'CONFIDENCE_OK' && r.code !== 'FRONT_DOOR' && !(r.code === 'PROFILE_DEFAULT' && r.severity === 'INFO'))
  const sentToDoor = run.decision.reasons.some((r) => r.code === 'FRONT_DOOR') && order ? order.status : null

  // Which rule decided, in words (from primary_reason; "within every limit" when it went through on its own).
  const ruleKey = decision.outcome === 'AUTO' ? 'AUTO' : decision.primary_reason?.code
  const ruleWords = ruleKey ? t.ruleWords[ruleKey] : undefined

  // The lines as a table: the front door's (what was ordered or held) or the agent's pick.
  const rows = order
    ? order.lines.map((l) => ({
        key: l.product_id, name: tidyName(l.name), qty: l.quantity != null ? c.amountOf(l.quantity, l.unit) : '—',
        price: l.unit_price_cents != null ? c.money(l.unit_price_cents) : '—', total: l.line_total_cents != null ? c.money(l.line_total_cents) : '—',
      }))
    : chosen.map((l) => ({
        key: l.product.id, name: productName(l), qty: l.quantity?.quantity != null ? c.amountOf(l.quantity.quantity, l.quantity.sales_unit) : '—',
        price: l.quote?.price != null ? c.price(l.quote.price) : '—', total: l.line_total_cents != null ? c.money(l.line_total_cents) : '—',
      }))

  // "Needs your OK" with more than one deliverable option: they become cards; pick one, then approve it.
  // Labels come from the data only: Best match = the agent's pick, Cheaper = a lower total, Local = origin FI.
  const held = awaitingApproval ? (chosen[0] ?? null) : guess
  const pickable = held ? [held, ...others.filter(orderable)] : []
  const sel = pickable.find((l) => l.product.id === (selected ?? held?.product.id)) ?? null
  const tags = (l: Line) =>
    [
      l === held && t.tagBest,
      held?.line_total_cents != null && l !== held && l.line_total_cents != null && l.line_total_cents < held.line_total_cents && t.tagCheaper,
      l.facts?.origin?.toUpperCase() === 'FI' && t.tagLocal,
    ].filter((x): x is string => !!x)
  function approveSelected(target: Line | null = sel) {
    const sel = target
    if (!sel) return
    if (awaitingApproval && sel === held) return decide('approve')
    if (awaitingApproval) {
      // another option instead of the held order: the held one is rejected, the chosen one goes to the front door
      setPlacing(sel.product.id)
      return run_('place', async () => {
        await decideOrder(order!.order_id!, 'reject')
        return placeOrder({ requested_date: requestedDate, lines: [lineOrder(sel)] })
      })
    }
    return place([lineOrder(sel)], sel.product.id)
  }
  // Change quantity: the same request with the new amount, asked again (same delivery day).
  const asked = held?.quantity?.requested ?? null
  function changeQuantity(e: FormEvent) {
    e.preventDefault()
    const n = amount.trim()
    if (!n || !held || !onAskFor) return
    onAskFor(`${n} ${asked?.unit ?? ''} ${query ?? productName(held)}`.replace(/\s+/g, ' ').trim())
  }
  const decline = awaitingApproval ? () => decide('reject') : onRetry

  // Compare: the agent's pick and the deliverable alternatives (up to 4). Choosing works while something can still
  // be chosen: the held order or best guess (as Approve selected does), or after a refusal or rejection.
  const comparable = [...chosen.filter(orderable), ...others.filter(orderable)].slice(0, 4)
  const chooseFromCompare = held
    ? (l: Line) => {
        setSelected(l.product.id)
        void approveSelected(l)
      }
    : canChoose
      ? (l: Line) => place([lineOrder(l)], l.product.id)
      : null
  const compareTags = (l: Line) =>
    [
      l.chosen && t.tagBest,
      chosen[0]?.line_total_cents != null && !l.chosen && l.line_total_cents != null && l.line_total_cents < chosen[0].line_total_cents && t.tagCheaper,
      l.facts?.origin?.toUpperCase() === 'FI' && t.tagLocal,
    ].filter((x): x is string => !!x)
  const query = run.request.items.length === 1 ? run.request.items[0].query : null

  return (
    <>
      <section className={`answer dc dc-${tone}`} aria-label={t.aria}>
        <header className="dc-strip">
          <p className={`status ${tone}`}>{status}</p>
          <p className="dc-when num">
            {t.delivery} {c.day(requestedDate)}
          </p>
        </header>
        <div className="dc-body">
          <h2 ref={heading} tabIndex={-1} className="answer-text num">
            {head}
          </h2>
          {ruleWords && <p className="dc-rule">{t.decidedBy(ruleWords)}</p>}
          {signOff && <p className="signoff">{signOff}</p>}
          <p className="answer-sub" ref={reasonsRef}>
            {more && <>{more} </>}
            {what && <>{what}. </>}
            {total > 0 && (
              <>
                <strong>{c.money(split ? split.total_cents : total)}</strong> {t.exclVat}
                {split ? t.forBoth : ''}.
              </>
            )}
            {order?.status === 'confirmed' && <> {arrives(requestedDate, c)}</>}
            {!awaitingApproval && !split && !guess && order?.status !== 'confirmed' && order?.status !== 'rejected' && lead?.suggested_fix && (
              <> {lead.suggested_fix}</>
            )}
          </p>
          {confidence != null && (
            <p className={`sure num${confidence < CONFIDENT_AT ? ' unsure' : ''}`}>
              {c.matched(confidence)}
              {confidence < CONFIDENT_AT && chosen[0]?.confidence_reason && <span className="quiet">. {chosen[0].confidence_reason}</span>}
            </p>
          )}

          {!split && rows.length > 0 && pickable.length < 2 && (
            <table className="dc-table num">
              <thead>
                <tr>
                  <th scope="col">{t.colProduct}</th>
                  <th scope="col">{t.colAmount}</th>
                  <th scope="col">{t.colPrice}</th>
                  <th scope="col">{t.colTotal}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key}>
                    <th scope="row">{r.name}</th>
                    <td data-label={t.colAmount}>{r.qty}</td>
                    <td data-label={t.colPrice}>{r.price}</td>
                    <td data-label={t.colTotal}>{r.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {profileNote && (
            <p className="quiet small">
              {c.humanize(profileNote.message.split(': only')[0])}.{' '}
              {onPlain && canChoose && (
                <button type="button" className="link accent inline" onClick={() => onPlain(need)} disabled={busy !== null}>
                  {t.plainInstead(need)}
                </button>
              )}
            </p>
          )}
          {chosen.length === 1 && chosen[0].usual && <p className="quiet small">{t.usual}.</p>}
          {sentToDoor && (
            <p className="quiet small">
              {t.frontDoor(sentToDoor)}{' '}
              {onHistory && (
                <button type="button" className="link accent inline" onClick={onHistory}>
                  {t.seeHistory}
                </button>
              )}
            </p>
          )}

          {pickable.length >= 2 && !justDone && (
            <fieldset className="dc-options">
              <legend className="dc-legend">{t.pickOne}</legend>
              {pickable.map((l) => {
                const [, avail] = availability(l, c)
                return (
                  <label key={l.product.id} className={`dc-option${sel === l ? ' on' : ''}`}>
                    <input type="radio" name={`pick-${run.audit_id}`} checked={sel === l} onChange={() => setSelected(l.product.id)} disabled={busy !== null} />
                    <span className="dc-option-main">
                      {tags(l).length > 0 && (
                        <span className="dc-tags">
                          {tags(l).map((tag) => (
                            <span key={tag} className="dc-tag">
                              {tag}
                            </span>
                          ))}
                        </span>
                      )}
                      <span className="dc-option-name">{productName(l)}</span>
                      <span className="quiet small">
                        {l.quantity?.quantity != null && `${c.amountOf(l.quantity.quantity, l.quantity.sales_unit)} · `}
                        {avail}
                      </span>
                    </span>
                    <span className="dc-option-price num">{l.line_total_cents != null ? c.money(l.line_total_cents) : '—'}</span>
                  </label>
                )
              })}
            </fieldset>
          )}

          {pickable.length >= 2 && !justDone && sel && (
            <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
              <button type="button" className="btn" onClick={() => void approveSelected()} disabled={busy !== null || (awaitingApproval && !canDecide)}>
                {busy === 'approve'
                  ? t.approving
                  : busy === 'place'
                    ? t.ordering
                    : awaitingApproval
                    ? t.approveSelected(c.money(sel === held ? total : (sel.line_total_cents ?? 0)))
                    : t.orderSelected(c.money(sel.line_total_cents ?? 0))}
              </button>
              {onAskFor && (
                <button type="button" className="btn plain" aria-expanded={changing} onClick={() => setChanging((v) => !v)} disabled={busy !== null}>
                  {t.changeQty}
                </button>
              )}
              {decline && (
                <button type="button" className="btn plain dc-decline" onClick={decline} disabled={busy !== null || (awaitingApproval && !canDecide)}>
                  {busy === 'reject' ? t.rejecting : t.decline}
                </button>
              )}
              {awaitingApproval && !canDecide && <p className="hint note">{t.needKey}</p>}
            </div>
          )}

          {pickable.length < 2 && (awaitingApproval || justDone) && (
            <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
              {justDone ? (
                <button type="button" className="btn done" disabled>
                  {t.done}
                </button>
              ) : (
                <>
                  <button type="button" className="btn" onClick={() => decide('approve')} disabled={busy !== null || !canDecide}>
                    {busy === 'approve' ? t.approving : t.approve(c.money(total))}
                  </button>
                  {onAskFor && held && (
                    <button type="button" className="btn plain" aria-expanded={changing} onClick={() => setChanging((v) => !v)} disabled={busy !== null}>
                      {t.changeQty}
                    </button>
                  )}
                  <button type="button" className="btn plain dc-decline" onClick={() => decide('reject')} disabled={busy !== null || !canDecide}>
                    {busy === 'reject' ? t.rejecting : t.decline}
                  </button>
                  {!canDecide && <p className="hint note">{t.needKey}</p>}
                </>
              )}
            </div>
          )}
          {split && (
            <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
              <button
                type="button"
                className="btn"
                onClick={() => place(split.order_lines ?? split.lines.filter((l) => l.quantity != null).map((l) => ({ product_id: l.product_id, quantity: l.quantity! })))}
                disabled={busy !== null}
              >
                {placing === 'main' ? t.ordering : t.orderBoth(split.lines.length === 2, c.money(split.total_cents))}
              </button>
            </div>
          )}
          {pickable.length < 2 && (guess || (!order && run.decision.outcome === 'ASK_HUMAN')) && (
            <div className={`decide${reasonsSeen ? ' floating' : ''}`}>
              {guess && (
                <button type="button" className="btn" onClick={() => place([lineOrder(guess)])} disabled={busy !== null}>
                  {placing === 'main' ? t.ordering : t.orderIt(c.money(guess.line_total_cents!))}
                </button>
              )}
              {onAskFor && guess && (
                <button type="button" className="btn plain" aria-expanded={changing} onClick={() => setChanging((v) => !v)} disabled={busy !== null}>
                  {t.changeQty}
                </button>
              )}
              {onRetry && (
                <button type="button" className="btn plain" onClick={onRetry} disabled={busy !== null}>
                  {t.notThis}
                </button>
              )}
            </div>
          )}

          {comparable.length >= 2 && (
            <div>
              <button type="button" className="btn plain accent-text" aria-expanded={comparing} onClick={() => setComparing((v) => !v)}>
                {t.compare(comparable.length)}
              </button>
            </div>
          )}

          {changing && held && onAskFor && (
            <form className="dc-qty" onSubmit={changeQuantity}>
              <label htmlFor={`qty-${run.audit_id}`}>{t.newAmount}</label>
              <div className="dc-qty-row">
                <input
                  id={`qty-${run.audit_id}`}
                  className="guests-input num"
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step="any"
                  value={amount}
                  placeholder={asked ? String(asked.amount) : ''}
                  onChange={(e) => setAmount(e.target.value)}
                  autoFocus
                />
                {asked?.unit && <span className="quiet">{asked.unit}</span>}
                <button type="submit" className="btn" disabled={!amount.trim()}>
                  {t.askAgain}
                </button>
              </div>
            </form>
          )}

          {error && (
            <div className="problem" role="alert" ref={errorRef}>
              <strong>{c.UI.failed}</strong>
              {error}
            </div>
          )}
        </div>
      </section>

      {comparing && comparable.length >= 2 && (
        <Compare
          lines={comparable}
          tags={compareTags}
          onChoose={chooseFromCompare}
          chooseLabel={(l) => (awaitingApproval && l === held ? t.approveThis : t.choose)}
          busy={busy !== null}
          placing={placing}
          onClose={() => setComparing(false)}
        />
      )}
      {after}
      {split && <SplitRows alt={split} />}
      {subs.length > 0 && (
        <Substitutes subs={subs} pick={pickSub} busy={busy !== null} placing={placing} />
      )}

      <div className="more">
        {chosen.map((l) => (
          <details key={l.product.id}>
            <summary>{chosen.length === 1 && query ? t.whyThis(query) : t.why(productName(l))}</summary>
            <WhyThis line={l} />
          </details>
        ))}
        {otherReasons.length > 0 && (
          <details>
            <summary>{signOff ? t.neededOk : t.also(otherReasons.length)}</summary>
            <ul className="more-body">
              {otherReasons.map((r, i) => (
                <li key={i}>
                  <p>{c.humanize(r.message)}</p>
                  {r.suggested_fix && <p className="quiet small">{r.suggested_fix}</p>}
                </li>
              ))}
            </ul>
          </details>
        )}
        {others.length > 0 && pickable.length < 2 && (
          <details>
            <summary>{t.other(others.length)}</summary>
            <ul className="more-body">
              {others.map((l) => (
                <OtherOption
                  key={l.product.id}
                  line={l}
                  onOrder={canChoose && orderable(l) ? () => place([lineOrder(l)], l.product.id) : null}
                  busy={busy !== null}
                  placing={placing === l.product.id}
                />
              ))}
            </ul>
          </details>
        )}
        <details>
          <summary>{t.understood}</summary>
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
function splitHeadline(alt: AlternativeOrder, c: Copy): string {
  const [have, rest] = alt.lines
  if (!have || !rest || have.quantity == null || rest.quantity == null) return c.UI.result.splitFallback
  const a = tidyName(have.name), b = tidyName(rest.name)
  const extra = b.startsWith(a) ? b.slice(a.length).replace(/^[,\s]+/, '') : b
  return c.UI.result.split(c.count(have.quantity), c.count(rest.quantity), extra)
}

function availability(line: Line, c: Copy): [string, string] {
  const t = c.UI.result
  const q = line.quote
  if (!q) return ['bad', t.notQuoted]
  const blocking = q.flags.filter((f) => f !== 'quantity_unknown')
  if (blocking.length) return ['bad', `${blocking.map(c.flag).join('. ')}.`]
  const stock = q.flags.includes('quantity_unknown') || q.available_amount === null ? t.stockUnknown : c.stock(q.available_amount)
  const when = [q.order_cutoff && t.orderBy(c.dateTime(q.order_cutoff)), q.available_date && t.arrivesOn(c.day(q.available_date.slice(0, 10)))]
    .filter(Boolean)
    .join(', ')
  return [q.flags.includes('quantity_unknown') ? 'warn' : '', `${stock}${when ? `, ${when}` : ''}.`]
}

function facts(line: Line, c: Copy): string | null {
  const t = c.UI.result
  const f = line.facts
  const rel = f ? f.delivery_reliability : line.product.delivery_reliability
  const co2 = f ? f.carbon_kg_per_kg : line.product.carbon_kg_per_kg
  const parts = [
    rel != null && t.onTime(Math.round(rel * 100)),
    f?.origin && t.from(c.country(f.origin)),
    co2 != null && t.co2(c.count(co2)),
  ].filter(Boolean)
  return parts.length ? parts.join(' ') : null
}

function WhyThis({ line }: { line: Line }) {
  const c = useCopy()
  const [, avail] = availability(line, c)
  const q = line.quote
  const f = facts(line, c)
  return (
    <div className="more-body">
      {line.why && <p>{c.humanize(line.why)}</p>}
      {line.confidence != null && (
        <p className="quiet num">
          {c.matched(line.confidence)}.{line.confidence_reason && ` ${line.confidence_reason}`}
        </p>
      )}
      <p className="quiet">
        {avail}
        {q?.price != null && c.UI.result.per(c.price(q.price), c.unitName(line.quantity?.sales_unit || line.product.sales_unit))}
      </p>
      {f && <p className="quiet">{f}</p>}
      {line.quantity && <p className="quiet small">{line.quantity.explanation}</p>}
      {line.confidence != null && <p className="faint tiny">{c.CONFIDENCE_MEANS}</p>}
    </div>
  )
}

function OtherOption({ line, onOrder, busy, placing }: { line: Line; onOrder: (() => void) | null; busy: boolean; placing: boolean }) {
  const c = useCopy()
  const [tone, avail] = availability(line, c)
  const unsure = line.confidence != null && line.confidence < CONFIDENT_AT
  const why = tone === 'bad' ? avail : line.confidence != null ? c.matched(line.confidence) : line.why || avail
  return (
    <li className="option">
      <div>
        <p>{productName(line)}</p>
        {line.usual && <p className="quiet small">{c.UI.result.usual}</p>}
        <p className={`option-why num ${tone === 'bad' ? 'bad' : unsure ? 'warn' : ''}`}>{why}</p>
        {onOrder && (
          <button type="button" className="btn plain accent-text small-btn" onClick={onOrder} disabled={busy}>
            {placing ? c.UI.result.ordering : c.UI.result.orderInstead}
          </button>
        )}
      </div>
      <p className="option-side quiet">{line.line_total_cents !== null ? c.money(line.line_total_cents) : '—'}</p>
    </li>
  )
}

// Allergen-safe substitutes for a line Valio can't deliver, best first (the backend's order is kept).
function Substitutes({ subs, pick, busy, placing }: { subs: Substitute[]; pick: (s: Substitute) => Pick | null; busy: boolean; placing: string | null }) {
  const c = useCopy()
  const t = c.UI.result
  return (
    <section className="instead" aria-labelledby="subs-title">
      <h2 className="title" id="subs-title">
        {t.otherChoices}
      </h2>
      <ul>
        {subs.map((s) => (
          <li key={`${s.replaces}-${s.product_id}`} className="alt">
            <div>
              <p className="alt-rank">{t.rank[s.tier] ?? s.tier}</p>
              <p>{tidyName(s.name)}</p>
              <p className="quiet small">{s.why_safe}</p>
              {(() => {
                const p = pick(s)
                return (
                  p && (
                    <button type="button" className="btn plain accent-text small-btn" onClick={p.go} disabled={busy}>
                      {placing === s.product_id ? t.ordering : p.label}
                    </button>
                  )
                )
              })()}
            </div>
            <div className="alt-side">
              <p>{s.unit_price_cents !== null ? c.money(s.unit_price_cents) : '—'}</p>
              <p className="quiet small">{t.perUnit(c.unitName(s.unit))}</p>
              <p className="quiet small">
                {s.reliability !== null
                  ? t.onTimeShort(Math.round(s.reliability * 100))
                  : s.available !== null
                    ? c.stock(s.available)
                    : t.stockUnknown}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function SplitRows({ alt }: { alt: AlternativeOrder }) {
  const c = useCopy()
  const t = c.UI.result
  return (
    <section className="instead" aria-label={t.splitAria}>
      <div>
        {alt.lines.map((l) => (
          <div key={l.product_id} className="split-row">
            <span>
              {tidyName(l.name)}
              {l.replaces && <span className="quiet"> {t.substitute}</span>}
            </span>
            <span className="qty r">{l.quantity != null ? c.amountOf(l.quantity, l.unit) : '—'}</span>
            <span className="r">{l.line_total_cents !== null ? c.money(l.line_total_cents) : '—'}</span>
          </div>
        ))}
        <div className="split-total">
          <span>
            <strong>{c.money(alt.total_cents)}</strong> <span className="quiet">{t.inTotal}</span>
          </span>
        </div>
      </div>
    </section>
  )
}

// A backend sentence can run long ("…doesn't seem to stock X. Closest in the catalogue: A; B; C."): the first sentence
// is the headline, the rest reads under it, with SHOUTED catalogue names in normal case.
function splitLong(s: string, c: ReturnType<typeof useCopy>): [string, string | null] {
  const m = s.length > 80 ? /^(.+?[.!?])\s+(\S.*)$/s.exec(s) : null
  return m ? [m[1], m[2].replace(/\b[A-Z0-9][A-Z0-9 ]*[A-Z]{3}[A-Z0-9 ]*\b/g, (n) => c.tidyName(n))] : [s, null]
}
