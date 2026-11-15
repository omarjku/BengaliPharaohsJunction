import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { decideOrder, getKeys, getOrder, MOCK, placeOrder, rememberChoice } from './api'
import { CONFIDENT_AT, tidyName } from './copy'
import { errorText, type Tone } from './format'
import { useCopy, type Copy } from './i18n'
import type { AgentRun, AlternativeOrder, Line, OrderInput, OrderResponse, Substitute } from './types'
import './RunResult.css'
import { Compare } from './Compare'
import { heldLine, sameItem } from './heldLine'
import { Cart, type CartLine } from './Cart'
import { countryFlag, formatCartPack, formatSustainabilityLabel } from './cartFormat'

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
  onCartChange?: (order: OrderResponse) => void
  after?: ReactNode // shown right under the answer (e.g. "Need it sooner?"), before the details
}
type Busy = 'approve' | 'reject' | 'place' | null
type Pick = { label: string; go: () => void }

const productName = (l: Line) => tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Helsinki' })

const orderable = (l: Line) => l.quote != null && l.quote.orderable && l.quantity?.quantity != null && l.line_total_cents != null
const lineOrder = (l: Line) => ({ product_id: l.product.id, quantity: l.quantity!.quantity! })

export function RunResult({ run, requestedDate, onAction, onBusy, onAnnounce, onRetry, onHistory, onAskFor, onPlain, onCartChange, after }: Props) {
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
  // "Remember this choice?": offered after the chef ordered an option other than the agent's pick.
  const picked = useRef<string | null>(null)
  const [rememberId, setRememberId] = useState<string | null>(null)
  const [remembered, setRemembered] = useState<string | null>(null) // the scope, once saved
  const [rememberError, setRememberError] = useState<string | null>(null)
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
        ? ['warn', t.needsApproval]
        : order.status === 'rejected'
          ? ['bad', st.rejected]
          : order.status === 'refused'
            ? ['bad', st.notOrdered]
            : ['neutral', order.status]
    : run.decision.outcome === 'DECLINE'
      ? ['bad', st.notOrdered]
      : run.decision.outcome === 'ASK_HUMAN'
      ? ['warn', t.needsApproval]
        : ['neutral', st.sent]

  const lead = decision.reasons[0] ?? null
  const confidenceThreshold = run.confidence_threshold ?? CONFIDENT_AT
  const text =
    order?.status === 'confirmed'
      ? t.orderedFor(c.day(requestedDate))
      : order?.status === 'rejected'
        ? t.rejected
        : split
          ? splitHeadline(split, c)
          : lead
            ? c.headline(lead, confidenceThreshold)
            : status

  const total = order?.total_cents || chosen.reduce((a, l) => a + (l.line_total_cents ?? 0), 0)
  const buildCommit = order?.build?.commit ? order.build.commit.slice(0, 7) : 'unavailable'
  const buildSbom = order?.build?.sbom_sha256 ? order.build.sbom_sha256.slice(0, 12) : 'unavailable'
  const awaitingApproval = order?.status === 'pending_approval' && order.order_id !== null
  const canDecide = MOCK || Boolean(getKeys().approverKey)
  const cartReason = order?.status === 'confirmed' ? null : text === status ? null : text

  useEffect(() => {
    onAnnounce(`${status}. ${cartReason ?? ''}`.trim())
  }, [status, cartReason, result, onAnnounce])

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
      onCartChange?.(res)
      if (kind === 'place' && picked.current && picked.current !== 'main' && picked.current !== chosen[0]?.product.id && res.status !== 'refused')
        setRememberId(picked.current)
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
    picked.current = which
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

  // "Needs your OK" with more than one deliverable option: they become cards; pick one, then approve it.
  // Labels come from the data only: Best match = the agent's pick, Cheaper = a lower total, Local = origin FI.
  const held = awaitingApproval ? heldLine(order, run.lines, chosen[0] ?? null) : guess
  const pickable = held ? [held, ...others.filter((l) => orderable(l) && sameItem(l, held))] : []
  const sel = pickable.find((l) => l.product.id === (selected ?? held?.product.id)) ?? null
  const tags = (l: Line) =>
    [
      l === held && t.tagBest,
      held?.line_total_cents != null && l !== held && l.line_total_cents != null && l.line_total_cents < held.line_total_cents && t.tagCheaper,
      l.facts?.origin?.toUpperCase() === 'FI' && t.tagLocal,
    ].filter((x): x is string => !!x)
  const cartLine = (line: Line | undefined, fallback: { id: string; name: string; quantity: number | null; unit: string | null; unitPrice: string; total: string; deposit?: string | null }): CartLine => {
    const reliability = line?.facts?.delivery_reliability ?? line?.product.delivery_reliability ?? null
    const carbon = line?.facts?.carbon_kg_per_kg ?? line?.product.carbon_kg_per_kg ?? null
    const origin = line?.facts?.origin ?? null
    const availability = line ? availabilityForCart(line, c) : { tone: undefined, text: t.notReported }
    const quantityChanged = line?.quantity?.quantity != null && fallback.quantity != null && line.quantity.quantity !== fallback.quantity
    const packQuantity = quantityChanged && line?.quantity ? { ...line.quantity, quantity: fallback.quantity } : line?.quantity
    const pack = formatCartPack(packQuantity, { quantity: fallback.quantity, unit: fallback.unit }, c.count)
    const quantityMath = line?.quantity && !quantityChanged
      ? `${c.count(line.quantity.requested.amount)} ${line.quantity.requested.unit} = ${pack}`
      : pack
    const facts: CartLine['facts'] = []
    if (reliability != null) facts.push({ label: t.onTimeShort(Math.round(reliability * 100)), tone: reliability < 0.9 ? 'warn' : undefined })
    if (carbon != null) facts.push({ label: t.co2(c.count(carbon)).replace(/\.$/, '') })
    if (origin) facts.push({ label: `${countryFlag(origin)} ${c.country(origin)}`.trim() })
    for (const label of (line?.facts?.labels ?? line?.product.claims ?? []).slice(0, 3)) facts.push({ label: formatSustainabilityLabel(label) })
    if (line?.deposit ?? fallback.deposit) facts.push({ label: t.deposit })
    return {
      id: fallback.id,
      name: fallback.name,
      pack,
      unitPrice: fallback.unitPrice,
      total: fallback.total,
      facts,
      confidence: line?.confidence != null && (line.confidence < confidenceThreshold || line === held) ? t.check(c.pct(line.confidence)) : null,
      why: [
        { label: t.cmp.match, value: line?.confidence != null ? c.pct(line.confidence) : line?.usual ? t.usual : line?.chosen ? t.tagBest : t.notReported },
        { label: t.colAmount, value: quantityMath },
        { label: t.cmp.stock, value: availability.text, tone: availability.tone },
      ],
    }
  }
  const cartRows = split?.lines ?? order?.lines
  const cartLines = cartRows
    ? cartRows.map((line) => {
        const source = run.lines.find((candidate) => candidate.product.id === line.product_id)
        return cartLine(source, {
          id: line.product_id,
          name: tidyName(line.name),
          quantity: line.quantity,
          unit: line.unit,
          unitPrice: line.unit_price_cents != null ? c.money(line.unit_price_cents) : '—',
          total: line.line_total_cents != null ? c.money(line.line_total_cents) : '—',
          deposit: line.deposit,
        })
      })
    : chosen.map((line) =>
        cartLine(line, {
          id: line.product.id,
          name: productName(line),
          quantity: line.quantity?.quantity ?? null,
          unit: line.quantity?.sales_unit ?? line.product.sales_unit,
          unitPrice: line.quote?.price != null ? c.price(line.quote.price) : '—',
          total: line.line_total_cents != null ? c.money(line.line_total_cents) : '—',
        }),
      )
  function approveSelected(target: Line | null = sel) {
    const sel = target
    if (!sel) return
    if (awaitingApproval && sel === held) return decide('approve')
    if (awaitingApproval) {
      // another option instead of the held order: the held one is rejected, the chosen one goes to the front door
      setPlacing(sel.product.id)
      picked.current = sel.product.id
      return run_('place', approved(async () => {
        await decideOrder(order!.order_id!, 'reject')
        return placeOrder({ requested_date: requestedDate, lines: [lineOrder(sel)] })
      }))
    }
    setPlacing(sel.product.id)
    picked.current = sel.product.id
    return run_('place', approved(() => placeOrder({ requested_date: requestedDate, lines: [lineOrder(sel)] })))
  }
  // "Approve selected" is the chef's approval: if the front door holds the chosen option for sign-off (e.g. no
  // reliability data), approve it in the same tap instead of showing another "Needs your OK" (approver key only).
  const approved = (go: () => Promise<OrderResponse>) => async () => {
    const res = await go()
    if (!MOCK && res.status === 'pending_approval' && res.order_id && getKeys().approverKey) return decideOrder(res.order_id, 'approve')
    return res
  }
  // POST /api/profile/memories (approver key): a near-tie breaker only, never past the checks or the limits.
  async function remember(scope: 'this_order' | 'always') {
    if (!rememberId) return
    setRememberError(null)
    try {
      await rememberChoice(rememberId, scope)
      setRemembered(scope)
    } catch (err) {
      setRememberError(errorText(err))
    }
  }
  // Kitchen loss on a direct order: one tap of spare, offered with its cost, never added silently. Before anything is
  // ordered it re-asks with the larger amount; after a confirmed order it asks for just the extra (no second full order).
  const spareTip = chosen.length === 1 ? (chosen[0].spare_suggestion ?? null) : null
  const query = run.request.items.length === 1 ? run.request.items[0].query : null
  function addSpare() {
    if (!spareTip || !onAskFor) return
    const asked = chosen[0].quantity?.requested
    const name = query ?? productName(chosen[0])
    const extra = spareTip.extra_quantity
    const unit = spareTip.unit ?? asked?.unit ?? ''
    if (order?.status === 'confirmed' || !asked) onAskFor(`${extra} ${unit} ${name}`.replace(/\s+/g, ' ').trim())
    else onAskFor(`${Math.round((asked.amount + extra) * 1000) / 1000} ${unit} ${name}`.replace(/\s+/g, ' ').trim())
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
  const comparable = [...chosen.filter((l) => orderable(l) && (chosen.length === 1 || l === (held ?? chosen[0]))), ...others.filter((l) => orderable(l) && sameItem(l, held ?? chosen[0]))].slice(0, 4)
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
  return (
    <>
      <Cart
        id={`cart-${run.audit_id}`}
        status={status}
        tone={tone}
        delivery={c.day(requestedDate)}
        reason={cartReason}
        lines={cartLines}
        total={c.money(split ? split.total_cents : total)}
        autoScroll
        ariaLabel={t.aria}
        body={
          <>
            {run.changes?.map((change) => (
              <p key={`${change.item}-${change.from}-${change.to}`} className="quiet small">
                {t.changed(change.from, change.to)}
              </p>
            ))}
            {signOff && <p className="signoff">{signOff}</p>}
            {order?.build && (
              <p className="quiet small">
                {t.signedByBuild} <span dir="ltr">{buildCommit} · SBOM {buildSbom}</span>
              </p>
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
            {spareTip && (
              <p className="quiet small">
                {spareTip.extra_quantity > 0 && onAskFor && order?.status !== 'pending_approval' ? (
                  <button type="button" className="btn plain accent-text" onClick={addSpare} disabled={busy !== null}>
                    {t.addSpare(`${c.count(spareTip.extra_quantity)} ${spareTip.unit ?? ''}`.trim(), c.money(spareTip.extra_cost_cents))}
                  </button>
                ) : null}{' '}
                {spareTip.reason}
              </p>
            )}
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
                {pickable.map((line) => {
                  const [, avail] = availability(line, c)
                  return (
                    <label key={line.product.id} className={`dc-option${sel === line ? ' on' : ''}`}>
                      <input type="radio" name={`pick-${run.audit_id}`} checked={sel === line} onChange={() => setSelected(line.product.id)} disabled={busy !== null} />
                      <span className="dc-option-main">
                        {tags(line).length > 0 && (
                          <span className="dc-tags">
                            {tags(line).map((tag) => <span key={tag} className="dc-tag">{tag}</span>)}
                          </span>
                        )}
                        <span className="dc-option-name">{productName(line)}</span>
                        <span className="quiet small">{formatCartPack(line.quantity, undefined, c.count)} · {avail}</span>
                      </span>
                      <span className="dc-option-price num">{line.line_total_cents != null ? c.money(line.line_total_cents) : '—'}</span>
                    </label>
                  )
                })}
              </fieldset>
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
                  <button type="submit" className="btn" disabled={!amount.trim()}>{t.askAgain}</button>
                </div>
              </form>
            )}
            {error && (
              <div className="problem" role="alert" ref={errorRef}>
                <strong>{c.UI.failed}</strong>
                {error}
              </div>
            )}
            {rememberId && !remembered && (MOCK || !!getKeys().approverKey) && (
              <div className="dc-remember">
                <p>{t.rememberQ(productName(run.lines.find((line) => line.product.id === rememberId) ?? chosen[0]))}</p>
                <div className="actions">
                  <button type="button" className="btn plain accent-text" onClick={() => void remember('this_order')}>{t.rememberOrder}</button>
                  <button type="button" className="btn plain accent-text" onClick={() => void remember('always')}>{t.rememberAlways}</button>
                  <button type="button" className="btn plain" onClick={() => setRememberId(null)}>{t.rememberNo}</button>
                </div>
                {rememberError && <p className="photo-error small">{rememberError}</p>}
              </div>
            )}
            {remembered && <p className="quiet small" role="status">{t.remembered(remembered)}</p>}
          </>
        }
        footer={
          <>
            {pickable.length >= 2 && !justDone && sel && (
              <div className="decide">
                <button type="button" className="btn" onClick={() => void approveSelected()} disabled={busy !== null || (awaitingApproval && !canDecide)}>
                  {busy === 'approve'
                    ? t.approving
                    : busy === 'place'
                      ? t.ordering
                      : awaitingApproval
                        ? t.approveSelected(c.money(sel === held ? total : (sel.line_total_cents ?? 0)))
                        : t.orderSelected(c.money(sel.line_total_cents ?? 0))}
                </button>
                {onAskFor && <button type="button" className="btn plain" aria-expanded={changing} onClick={() => setChanging((v) => !v)} disabled={busy !== null}>{t.changeQty}</button>}
                {decline && <button type="button" className="btn plain dc-decline" onClick={decline} disabled={busy !== null || (awaitingApproval && !canDecide)}>{busy === 'reject' ? t.rejecting : t.decline}</button>}
                {awaitingApproval && !canDecide && <p className="hint note">{t.needKey}</p>}
              </div>
            )}
            {pickable.length < 2 && (awaitingApproval || justDone) && (
              <div className="decide">
                {justDone ? (
                  <button type="button" className="btn done" disabled>{t.done}</button>
                ) : (
                  <>
                    <button type="button" className="btn" onClick={() => decide('approve')} disabled={busy !== null || !canDecide}>{busy === 'approve' ? t.approving : t.approve(c.money(total))}</button>
                    {onAskFor && held && <button type="button" className="btn plain" aria-expanded={changing} onClick={() => setChanging((v) => !v)} disabled={busy !== null}>{t.changeQty}</button>}
                    <button type="button" className="btn plain dc-decline" onClick={() => decide('reject')} disabled={busy !== null || !canDecide}>{busy === 'reject' ? t.rejecting : t.decline}</button>
                    {!canDecide && <p className="hint note">{t.needKey}</p>}
                  </>
                )}
              </div>
            )}
            {split && (
              <div className="decide">
                <button type="button" className="btn" onClick={() => place(split.order_lines ?? split.lines.filter((line) => line.quantity != null).map((line) => ({ product_id: line.product_id, quantity: line.quantity! })))} disabled={busy !== null}>
                  {placing === 'main' ? t.ordering : t.orderBoth(split.lines.length === 2, c.money(split.total_cents))}
                </button>
              </div>
            )}
            {pickable.length < 2 && (guess || (!order && run.decision.outcome === 'ASK_HUMAN')) && (
              <div className="decide">
                {guess && <button type="button" className="btn" onClick={() => place([lineOrder(guess)])} disabled={busy !== null}>{placing === 'main' ? t.ordering : t.orderIt(c.money(guess.line_total_cents!))}</button>}
                {onAskFor && guess && <button type="button" className="btn plain" aria-expanded={changing} onClick={() => setChanging((v) => !v)} disabled={busy !== null}>{t.changeQty}</button>}
                {onRetry && <button type="button" className="btn plain" onClick={onRetry} disabled={busy !== null}>{t.notThis}</button>}
              </div>
            )}
          </>
        }
      />

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
      {subs.length > 0 && (
        <Substitutes subs={subs} pick={pickSub} busy={busy !== null} placing={placing} />
      )}

      <div className="more">
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
                  threshold={confidenceThreshold}
                  onOrder={canChoose && orderable(l) ? () => place([lineOrder(l)], l.product.id) : null}
                  busy={busy !== null}
                  placing={placing === l.product.id}
                />
              ))}
            </ul>
          </details>
        )}
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

function availabilityForCart(line: Line, c: Copy): { tone: Tone | undefined; text: string } {
  const [tone, text] = availability(line, c)
  return { tone: tone === 'bad' || tone === 'warn' ? tone : undefined, text }
}

function OtherOption({ line, threshold, onOrder, busy, placing }: { line: Line; threshold: number; onOrder: (() => void) | null; busy: boolean; placing: boolean }) {
  const c = useCopy()
  const [tone, avail] = availability(line, c)
  const unsure = line.confidence != null && line.confidence < threshold
  const why = tone === 'bad' ? avail : line.confidence != null ? c.matched(line.confidence, threshold) : line.why || avail
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
