import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getKeys, MOCK, placeOrder, planMenu } from './api'
import { tidyName } from './copy'
import { errorText } from './format'
import { useCopy } from './i18n'
import { RunResult } from './RunResult'
import type { Line, MenuRun, OrderResponse, PortionOverride } from './types'
import './Menu.css'

type Props = {
  plan: MenuRun
  covers: number | null // from the ask response, when the backend reports it
  requestedDate: string
  onAction: () => void // something was ordered (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (text: string) => void
  after?: ReactNode // shown right under the answer, before the cart
  have?: string[] // what the kitchen has for this order only (a pantry photo): sent with every re-plan
  onReplanned?: (plan: MenuRun) => void // the cart changed: the thread's line above the card is rewritten
  menuText?: string // the chef's menu as asked: with it, portions can be changed and the cart re-planned
}
const UNITS = ['L', 'dl', 'cl', 'ml', 'kg', 'g', 'pcs'] as const

const productName = (l: Line) => tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)
const orderable = (l: Line) => l.quote != null && l.quote.orderable && l.quantity?.quantity != null && l.line_total_cents != null

// A menu became a proposed cart: the chef checks the portions, then orders the cart as one order.
export function MenuResult({ plan: proposed, covers, requestedDate, onAction, onBusy, onAnnounce, after, menuText, have, onReplanned }: Props) {
  // The plan on screen: the proposal, or the re-plan after the chef changed portions.
  const [plan, setPlan] = useState(proposed)
  const [portions, setPortions] = useState<Record<string, string>>({}) // "dish|ingredient" -> the chef's amount per portion
  const [spares, setSpares] = useState<Record<string, string>>({}) // ingredient -> the chef's spare percent (0-20)
  const [replanning, setReplanning] = useState(false)
  const [back, setBack] = useState<Set<string>>(new Set()) // left-out ingredients the chef chose to buy anyway (include)
  const canEdit = !!menuText && covers != null
  const planFor = { covers, date: requestedDate }
  const c = useCopy()
  const t = c.UI.menu
  const amount = (n: number | null, unit: string | null) => [n != null ? c.count(n) : null, unit].filter(Boolean).join(' ')
  const [ordering, setOrdering] = useState(false)
  const [ordered, setOrdered] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The chef's own picks: ingredient index -> the option chosen instead of the agent's (or for an empty slot).
  const [swap, setSwap] = useState<Record<number, Line>>({})
  const swapped = Object.entries(swap).map(([i, l]) => [Number(i), l] as const)
  const replaced = plan.lines.filter((l) => l.chosen && l.item != null && swap[l.item] !== undefined)
  // ponytail: a product the agent chose for two ingredients is one order line; swapping one ingredient drops both.
  // Doubted lines ("check this") are left out of order_lines by the backend; the chef adds each one deliberately.
  const [added, setAdded] = useState<Set<string>>(new Set())
  const addedLines = plan.lines.filter((l) => l.check && added.has(l.product.id) && orderable(l) && (l.item == null || swap[l.item] === undefined))
  const orderLines = [
    ...plan.order_lines.filter((o) => !replaced.some((l) => l.product.id === o.product_id)),
    ...[...swapped.map(([, l]) => l), ...addedLines].map((l) => ({ product_id: l.product.id, quantity: l.quantity!.quantity! })),
  ]
  const total =
    plan.cart_total_cents -
    replaced.filter((l) => !l.check).reduce((a, l) => a + (l.line_total_cents ?? 0), 0) +
    [...swapped.map(([, l]) => l), ...addedLines].reduce((a, l) => a + (l.line_total_cents ?? 0), 0)
  const toggleAdd = (id: string) =>
    setAdded((s) => {
      const next = new Set(s)
      if (!next.delete(id)) next.add(id)
      return next
    })
  const choose = (i: number, l: Line) =>
    setSwap((s) => {
      const next = { ...s }
      if (l.chosen) delete next[i] // back to the agent's pick
      else next[i] = l
      return next
    })
  // Changed portions -> overrides; "Update the cart" re-plans with them (Room 3: POST /api/agent/menu overrides).
  const changed: PortionOverride[] = [
    ...plan.menu.dishes.flatMap((d) =>
      d.ingredients.flatMap((i) => {
        const v = portions[`${d.name}|${i.name}`]
        const n = v == null || v.trim() === '' ? null : Number(v)
        if (n == null || !Number.isFinite(n) || n <= 0 || n === i.per_cover || !i.unit || !(UNITS as readonly string[]).includes(i.unit)) return []
        return [{ ingredient: i.name, per_cover: n, unit: i.unit as PortionOverride['unit'], dish: d.name }]
      }),
    ),
    // spare per ingredient (0-20 %), the chef's own
    ...plan.ingredients.flatMap((ing) => {
      const v = spares[ing.query]
      const n = v == null || v.trim() === '' ? null : Number(v)
      if (n == null || !Number.isFinite(n) || n < 0 || n > 20 || n === ing.spare_percent) return []
      return [{ ingredient: ing.query, spare_percent: n }]
    }),
  ]
  const pendingBack = plan.ingredients.filter((ing) => ing.have && back.has(ing.query)).length
  // The cart's spare in one sentence, with its cost (never presented as free).
  const spareNote = plan.decision.reasons.find((r) => r.code === 'MENU_ASSUMPTIONS' && typeof r.facts.spare_percent === 'number')
  const sparePct = spareNote ? Number(spareNote.facts.spare_percent) : 0
  const spareRounding = spareNote && typeof spareNote.facts.from_rounding === 'number' ? Number(spareNote.facts.from_rounding) : 0
  const spareCost = sparePct > 0 ? Math.round(plan.cart_total_cents - plan.cart_total_cents / (1 + sparePct / 100)) : 0
  // One ingredient's spare cost: what the chosen line buys beyond what the recipe needs (spare + pack rounding).
  const spareCostOf = (l: Line | undefined, needed: number | null | undefined) => {
    const got = l?.quantity?.delivered
    return l?.line_total_cents != null && got && needed != null && got > needed ? Math.round(l.line_total_cents * (1 - needed / got)) : 0
  }
  async function replan() {
    if (!menuText || covers == null || !changed.length) return
    if (!MOCK && !getKeys().agentKey) return setError(c.UI.result.keysFirst)
    setReplanning(true)
    onBusy(true)
    setError(null)
    try {
      const next = await planMenu({
        menu_text: menuText,
        covers,
        requested_date: planFor.date,
        overrides: [...changed, ...[...back].map((ingredient) => ({ ingredient, include: true }))],
        ...(have?.length ? { have } : {}),
      })
      setPlan(next)
      onReplanned?.(next)
      setPortions({})
      setSpares({})
      setSwap({})
      setAdded(new Set())
      onAnnounce(t.announce(forWhom, c.money(next.cart_total_cents)))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setReplanning(false)
      onBusy(false)
    }
  }
  const heading = useRef<HTMLHeadingElement>(null)
  // The order button comes after the cart, and on a phone it floats only once the total has been seen.
  const totalRef = useRef<HTMLDivElement>(null)
  const [totalSeen, setTotalSeen] = useState(false)
  useEffect(() => {
    const el = totalRef.current
    if (!el || totalSeen) return
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setTotalSeen(true), { threshold: 1 })
    io.observe(el)
    return () => io.disconnect()
  })
  // The decision's reasons about a product in the cart (not the generic 'amounts are estimates' one).
  const concerns = (l: Line) =>
    plan.decision.reasons.filter((r) => r.product_id === l.product.id && r.severity !== 'INFO' && r.code !== 'MENU_ASSUMPTIONS')
  const forWhom = covers ? t.forGuests(c.count(covers)) : t.forMenu

  useEffect(() => {
    onAnnounce(t.announce(forWhom, c.money(plan.cart_total_cents)))
    heading.current?.focus()
  }, [plan, forWhom, onAnnounce, t, c])

  async function orderCart() {
    if (!MOCK && !getKeys().agentKey) return setError(c.UI.result.keysFirst)
    setOrdering(true)
    onBusy(true)
    setError(null)
    try {
      setOrdered(await placeOrder({ requested_date: planFor.date, lines: orderLines })) // as proposed, with the chef's picks
      onAction()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setOrdering(false)
      onBusy(false)
    }
  }

  return (
    <>
      {error && (
        <div className="problem" role="alert">
          <strong>{c.UI.failed}</strong>
          {error}
        </div>
      )}

      {ordered && (
        <RunResult
          key={ordered.audit_id}
          run={{
            request: { summary: t.summary(forWhom), items: plan.ingredients },
            lines: plan.lines,
            decision: plan.decision,
            order: ordered,
            audit_id: ordered.audit_id,
          }}
          requestedDate={planFor.date}
          onAction={onAction}
          onBusy={onBusy}
          onAnnounce={onAnnounce}
        />
      )}

      {!ordered && (
        <>
          <section className="answer" aria-label={t.aria}>
            <p className="status neutral">{c.UI.status.ready}</p>
            <h2 ref={heading} tabIndex={-1} className="answer-text">
              {t.cart(forWhom, c.money(total))}
            </h2>
            <p className="answer-sub">
              {t.sub(c.day(planFor.date))}
            </p>
          </section>

          {after}
          <section className="instead mt-step" aria-labelledby="menu-step1">
            <StepHead n={1} id="menu-step1" title={t.step1} sub={t.step1Sub(covers != null ? c.count(covers) : null, c.day(planFor.date))} />
            <ul className="mt-dishes">
              {plan.menu.dishes.map((d) => (
                <li key={d.name}>{d.name}</li>
              ))}
            </ul>
          </section>

          <section className="instead mt-step" aria-labelledby="menu-dishes">
            <StepHead n={2} id="menu-dishes" title={t.step2} sub={t.step2Sub} />
            <div className="mt-dish-grid">
              {plan.menu.dishes.map((d) => (
                <article key={d.name} className="mt-dish">
                  <header className="mt-dish-head">
                    <h3>{d.name}</h3>
                    {covers != null && <span className="mt-covers num">{t.forGuests(c.count(covers))}</span>}
                  </header>
                  <ul>
                    {d.ingredients.map((i, k) => (
                      <li key={k} className="mt-ing">
                        <span className="mt-ing-name">{i.name}</span>
                        <span className="mt-ing-total num">
                          {i.per_cover != null && covers != null ? amount(round(i.per_cover * covers), i.unit) : t.amountUnclear}
                        </span>
                        {canEdit && i.unit && (UNITS as readonly string[]).includes(i.unit) ? (
                          <label className="mt-ing-per quiet small">
                            <input
                              className="mt-portion num"
                              type="number"
                              inputMode="decimal"
                              min={0}
                              step="any"
                              value={portions[`${d.name}|${i.name}`] ?? (i.per_cover != null ? String(i.per_cover) : '')}
                              onChange={(e) => setPortions((p) => ({ ...p, [`${d.name}|${i.name}`]: e.target.value }))}
                              aria-label={t.portionAria(i.name, d.name)}
                              disabled={replanning || !!ordered}
                            />{' '}
                            {t.perPortion(i.unit)}
                            {plan.assumptions.some((a) => a.dish === d.name && a.ingredient === i.name && a.set_by === 'chef') && (
                              <span className="mt-yours"> · {t.yours}</span>
                            )}
                          </label>
                        ) : (
                          <span className="mt-ing-per quiet small num">{i.per_cover != null ? t.perCover(amount(i.per_cover, i.unit)) : ''}</span>
                        )}
                        {i.assumption && <span className="mt-ing-why quiet small">{i.assumption}</span>}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
            {(changed.length > 0 || pendingBack > 0) && (
              <div className="actions mt-replan">
                <button type="button" className="btn" onClick={() => void replan()} disabled={replanning}>
                  {replanning ? t.updating : t.update(changed.length + pendingBack)}
                </button>
                <button type="button" className="btn plain" onClick={() => (setPortions({}), setSpares({}), setBack(new Set()))} disabled={replanning}>
                  {t.undoPortions}
                </button>
              </div>
            )}
          </section>

          <section className="instead mt-step" aria-labelledby="menu-cart">
            <StepHead n={3} id="menu-cart" title={t.theCart} sub={t.step3Sub(c.money(total))} />
            {plan.cart_coverage && (plan.cart_coverage.to_check > 0 || plan.cart_coverage.not_found.length > 0 || plan.cart_coverage.have > 0) && (
              <p className="mt-coverage small">
                {t.coverage(c.money(plan.cart_total_cents), plan.cart_coverage.in_cart, plan.cart_coverage.ingredients, plan.cart_coverage.to_check, c.money(plan.cart_coverage.check_total_cents), plan.cart_coverage.have)}
              </p>
            )}
            {sparePct > 0 && <p className="mt-spare-total small">{t.spareTotal(c.count(Math.round(sparePct)), c.money(spareCost), c.count(Math.round(spareRounding)))}</p>}
            {plan.ingredients.map((ing, i) => {
              const lines = plan.lines.filter((l) => l.item === i)
              const chosen = swap[i] ? [swap[i]] : lines.filter((l) => l.chosen)
              const others = lines.filter((l) => !chosen.includes(l))
              return (
                <div key={i} className="cart-group">
                  <p className="dish">
                    {amount(ing.amount, ing.unit)} {ing.query}
                  </p>
                  <p className="quiet small">{t.forDishes(ing.dishes)}</p>
                  {ing.needed_amount != null && ing.spare_percent != null && (
                    <div className="mt-spare quiet small">
                      <span>
                        {t.spareLine(amount(ing.needed_amount, ing.unit), c.count(ing.spare_percent))}
                        {spareCostOf(chosen[0], ing.needed_amount) > 0 && <> {t.spareCost(c.money(spareCostOf(chosen[0], ing.needed_amount)))}</>}
                      </span>
                      {canEdit && (
                        <label className="mt-spare-edit">
                          <input
                            className="mt-portion num"
                            type="number"
                            inputMode="numeric"
                            min={0}
                            max={20}
                            step={1}
                            value={spares[ing.query] ?? String(ing.spare_percent)}
                            onChange={(e) => setSpares((s) => ({ ...s, [ing.query]: e.target.value }))}
                            aria-label={t.spareAria(ing.query)}
                            disabled={replanning || !!ordered}
                          />{' '}
                          {t.spareUnit}
                        </label>
                      )}
                      {ing.spare_reason && <span className="mt-spare-why">{ing.spare_reason}</span>}
                    </div>
                  )}
                  {ing.have && (
                    <p className="mt-have">
                      <span className="option-why">{t.youHave(ing.have.matched, ing.have.source === 'this_order')}</span>{' '}
                      {canEdit && (
                        <button
                          type="button"
                          className="link accent inline"
                          aria-pressed={back.has(ing.query)}
                          onClick={() => setBack((b) => { const n = new Set(b); if (!n.delete(ing.query)) n.add(ing.query); return n })}
                          disabled={replanning}
                        >
                          {back.has(ing.query) ? t.addAnywayOn : t.addAnyway}
                        </button>
                      )}
                    </p>
                  )}
                  {chosen.length === 0 && !ing.have && (
                    <p className="option-why warn">
                      {others.length ? t.noConfident : t.nothingFits}
                    </p>
                  )}
                  {chosen.map((l) => (
                    <div key={l.product.id} className="split-row">
                      <span>{productName(l)}</span>
                      <span className="qty r">
                        {l.quantity?.quantity != null ? c.amountOf(l.quantity.quantity, l.quantity.sales_unit) : t.amountUnclear}
                      </span>
                      <span className="r">{l.line_total_cents !== null ? c.money(l.line_total_cents) : '—'}</span>
                      {concerns(l).map((r, k) => (
                        <span key={k} className="option-why warn concern">
                          {c.headline({ ...r, message: c.humanize(r.message) })}
                        </span>
                      ))}
                      {l.usual && <span className="quiet small concern">{c.UI.result.usual}</span>}
                      {l.check && !swap[i] && (
                        <span className="concern">
                          <span className="option-why warn">{added.has(l.product.id) ? c.UI.result.added : c.UI.result.checkThis}</span>{' '}
                          {orderable(l) && (
                            <button type="button" className="link accent inline" aria-pressed={added.has(l.product.id)} onClick={() => toggleAdd(l.product.id)} disabled={ordering}>
                              {added.has(l.product.id) ? c.UI.rules.undo : c.UI.result.addToOrder}
                            </button>
                          )}
                        </span>
                      )}
                    </div>
                  ))}
                  {others.length > 0 && (
                    <details>
                      <summary className="small">{c.UI.result.other(others.length)}</summary>
                      <ul className="more-body">
                        {others.map((l) => (
                          <li key={l.product.id} className="option">
                            <div>
                              <p>{productName(l)}</p>
                              {orderable(l) && (
                                <button type="button" className="btn plain accent-text small-btn" onClick={() => choose(i, l)} disabled={ordering}>
                                  {c.UI.result.orderInstead}
                                </button>
                              )}
                            </div>
                            <span className="option-side quiet">{l.line_total_cents !== null ? c.money(l.line_total_cents) : '—'}</span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )
            })}
            <div className="split-total" ref={totalRef}>
              <span>
                <strong className="num">{c.money(total)}</strong> <span className="quiet">{c.UI.result.exclVat}</span>
              </span>
            </div>
            {(changed.length > 0 || pendingBack > 0) && (
              <div className="actions mt-replan">
                <button type="button" className="btn" onClick={() => void replan()} disabled={replanning}>
                  {replanning ? t.updating : t.update(changed.length + pendingBack)}
                </button>
                <button type="button" className="btn plain" onClick={() => (setPortions({}), setSpares({}), setBack(new Set()))} disabled={replanning}>
                  {t.undoPortions}
                </button>
              </div>
            )}
            {orderLines.length > 0 && changed.length === 0 && pendingBack === 0 && (
              <div className={`decide${totalSeen ? ' floating' : ''}`}>
                <button type="button" className="btn" onClick={orderCart} disabled={ordering}>
                  {ordering ? c.UI.result.ordering : t.orderCart(c.money(total))}
                </button>
              </div>
            )}
          </section>

        </>
      )}
    </>
  )
}

// A numbered step header (the menu really is a sequence: the menu, its portions, the cart).
function StepHead({ n, id, title, sub }: { n: number; id: string; title: string; sub: string }) {
  return (
    <div className="mt-step-head">
      <span className="mt-step-n num" aria-hidden="true">
        {n}
      </span>
      <div>
        <h2 className="title" id={id}>
          {title}
        </h2>
        <p className="quiet small">{sub}</p>
      </div>
    </div>
  )
}

// Totals for display: per cover x guests, to 2 decimals at most (1.85 kg, not 1.8500000001).
const round = (n: number) => Math.round(n * 100) / 100
