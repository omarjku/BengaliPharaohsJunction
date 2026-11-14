import { useEffect, useRef, useState } from 'react'
import { placeOrder } from './api'
import { amountOf, headline, humanize, tidyName } from './copy'
import { errorText, formatCents, formatDay } from './format'
import { RunResult } from './RunResult'
import type { Line, MenuRun, OrderResponse } from './types'

type Props = {
  plan: MenuRun
  covers: number | null // from the ask response, when the backend reports it
  requestedDate: string
  onAction: () => void // something was ordered (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (text: string) => void
}

const productName = (l: Line) => tidyName(l.product.name_en ?? l.product.name_fi ?? l.product.id)
const amount = (n: number | null, unit: string | null) => [n?.toLocaleString('en-US'), unit].filter(Boolean).join(' ')
const and = (xs: string[]) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`)

// A menu became a proposed cart: the chef checks the portions, then orders the cart as one order.
export function MenuResult({ plan, covers, requestedDate, onAction, onBusy, onAnnounce }: Props) {
  const planFor = { covers, date: requestedDate }
  const [ordering, setOrdering] = useState(false)
  const [ordered, setOrdered] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
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
  const forWhom = covers ? `for ${covers.toLocaleString('en-US')} guests` : 'for your menu'

  useEffect(() => {
    onAnnounce(`Ready to order. A cart ${forWhom}, ${formatCents(plan.cart_total_cents)}.`)
    heading.current?.focus()
  }, [plan, forWhom, onAnnounce])

  async function orderCart() {
    setOrdering(true)
    onBusy(true)
    setError(null)
    try {
      setOrdered(await placeOrder({ requested_date: planFor.date, lines: plan.order_lines })) // verbatim, as proposed
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
          <strong>That didn’t go through.</strong>
          {error}
        </div>
      )}

      {ordered && (
        <RunResult
          key={ordered.audit_id}
          run={{
            request: { summary: `Menu ${forWhom}`, items: plan.ingredients },
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
          <section className="answer" aria-label="Proposed cart">
            <p className="status neutral">Ready to order</p>
            <h2 ref={heading} tabIndex={-1} className="answer-text">
              A cart {forWhom}, {formatCents(plan.cart_total_cents)}.
            </h2>
            <p className="answer-sub">
              Portions are estimates. Check them before you order. Delivery {formatDay(planFor.date)}, prices excl. VAT.
            </p>
          </section>

          <section className="instead" aria-labelledby="menu-cart">
            <h2 className="title" id="menu-cart">
              The cart
            </h2>
            {plan.ingredients.map((ing, i) => {
              const lines = plan.lines.filter((l) => l.item === i)
              const chosen = lines.filter((l) => l.chosen)
              const others = lines.filter((l) => !l.chosen)
              return (
                <div key={i} className="cart-group">
                  <p className="dish">
                    {amount(ing.amount, ing.unit)} {ing.query}
                  </p>
                  <p className="quiet small">For {and(ing.dishes)}</p>
                  {chosen.length === 0 && (
                    <p className="option-why warn">
                      {others.length ? 'No confident match, so nothing is in the cart for this. See the options.' : 'Nothing on Valio’s list fits this.'}
                    </p>
                  )}
                  {chosen.map((l) => (
                    <div key={l.product.id} className="split-row">
                      <span>{productName(l)}</span>
                      <span className="qty r">
                        {l.quantity?.quantity != null ? amountOf(l.quantity.quantity, l.quantity.sales_unit) : 'Amount unclear'}
                      </span>
                      <span className="r">{l.line_total_cents !== null ? formatCents(l.line_total_cents) : '—'}</span>
                      {concerns(l).map((r, k) => (
                        <span key={k} className="option-why warn concern">
                          {headline({ ...r, message: humanize(r.message) })}
                        </span>
                      ))}
                    </div>
                  ))}
                  {others.length > 0 && (
                    <details>
                      <summary className="small">Other options ({others.length})</summary>
                      <ul className="more-body">
                        {others.map((l) => (
                          <li key={l.product.id} className="option">
                            <span>{productName(l)}</span>
                            <span className="option-side quiet">{l.line_total_cents !== null ? formatCents(l.line_total_cents) : '—'}</span>
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
                <strong className="num">{formatCents(plan.cart_total_cents)}</strong> <span className="quiet">excl. VAT</span>
              </span>
            </div>
            {plan.order_lines.length > 0 && (
              <div className={`decide${totalSeen ? ' floating' : ''}`}>
                <button type="button" className="btn" onClick={orderCart} disabled={ordering}>
                  {ordering ? 'Ordering…' : `Order this cart · ${formatCents(plan.cart_total_cents)}`}
                </button>
              </div>
            )}
          </section>

          <section className="instead" aria-labelledby="menu-dishes">
            <h2 className="title" id="menu-dishes">
              Amounts per cover
            </h2>
            <div className="more flush">
              {plan.menu.dishes.map((d) => (
                <details key={d.name}>
                  <summary>
                    {d.name}
                    <span className="quiet small summary-count">
                      {d.ingredients.length} ingredients
                    </span>
                  </summary>
                  <ul className="more-body">
                    {d.ingredients.map((i, k) => (
                      <li key={k} className="option">
                        <div>
                          <p>{i.name}</p>
                          {i.assumption && <p className="quiet small">{i.assumption}</p>}
                        </div>
                        <p className="option-side quiet">{i.per_cover != null ? `${amount(i.per_cover, i.unit)} per cover` : 'Amount unclear'}</p>
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
