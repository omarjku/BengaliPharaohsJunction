import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getKeys, MOCK, placeOrder } from './api'
import { tidyName } from './copy'
import { errorText } from './format'
import { useCopy } from './i18n'
import { RunResult } from './RunResult'
import type { Line, MenuRun, OrderResponse } from './types'

type Props = {
  plan: MenuRun
  covers: number | null // from the ask response, when the backend reports it
  requestedDate: string
  onAction: () => void // something was ordered (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (text: string) => void
  after?: ReactNode // shown right under the answer, before the cart
}

const productName = (l: Line) => tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)
const orderable = (l: Line) => l.quote != null && l.quote.orderable && l.quantity?.quantity != null && l.line_total_cents != null

// A menu became a proposed cart: the chef checks the portions, then orders the cart as one order.
export function MenuResult({ plan, covers, requestedDate, onAction, onBusy, onAnnounce, after }: Props) {
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
  const orderLines = [
    ...plan.order_lines.filter((o) => !replaced.some((l) => l.product.id === o.product_id)),
    ...swapped.map(([, l]) => ({ product_id: l.product.id, quantity: l.quantity!.quantity! })),
  ]
  const total =
    plan.cart_total_cents - replaced.reduce((a, l) => a + (l.line_total_cents ?? 0), 0) + swapped.reduce((a, [, l]) => a + (l.line_total_cents ?? 0), 0)
  const choose = (i: number, l: Line) =>
    setSwap((s) => {
      const next = { ...s }
      if (l.chosen) delete next[i] // back to the agent's pick
      else next[i] = l
      return next
    })
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
          <section className="instead" aria-labelledby="menu-cart">
            <h2 className="title" id="menu-cart">
              {t.theCart}
            </h2>
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
                  {chosen.length === 0 && (
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
            {orderLines.length > 0 && (
              <div className={`decide${totalSeen ? ' floating' : ''}`}>
                <button type="button" className="btn" onClick={orderCart} disabled={ordering}>
                  {ordering ? c.UI.result.ordering : t.orderCart(c.money(total))}
                </button>
              </div>
            )}
          </section>

          <section className="instead" aria-labelledby="menu-dishes">
            <h2 className="title" id="menu-dishes">
              {t.amounts}
            </h2>
            <div className="more flush">
              {plan.menu.dishes.map((d) => (
                <details key={d.name}>
                  <summary>
                    {d.name}
                    <span className="quiet small summary-count">
                      {t.ingredients(d.ingredients.length)}
                    </span>
                  </summary>
                  <ul className="more-body">
                    {d.ingredients.map((i, k) => (
                      <li key={k} className="option">
                        <div>
                          <p>{i.name}</p>
                          {i.assumption && <p className="quiet small">{i.assumption}</p>}
                        </div>
                        <p className="option-side quiet">{i.per_cover != null ? t.perCover(amount(i.per_cover, i.unit)) : t.amountUnclear}</p>
                      </li>
                    ))}
                  </ul>
                </details>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  )
}
