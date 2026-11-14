import { useEffect, useRef, useState, type FormEvent } from 'react'
import { placeOrder, planMenu } from './api'
import { STATUS, unitName } from './copy'
import { errorText, formatCents, formatDay, nextMonday } from './format'
import { RunResult } from './RunResult'
import type { Line, MenuRun, OrderResponse } from './types'

type Props = {
  onAction: () => void // something was ordered (refresh the history)
  onBusy: (busy: boolean) => void
  onAnnounce: (text: string) => void
}

const MENU_EXAMPLE = 'Creamy salmon soup; lingonberry quark pie'
const PLANNING = 'Reading the menu, estimating amounts per cover, then checking Valio stock and prices…'
const productName = (l: Line) => l.product.name_en ?? l.product.name_fi ?? l.product.id
const amount = (n: number | null, unit: string | null) => [n?.toLocaleString('en-US'), unit].filter(Boolean).join(' ')
const and = (xs: string[]) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`)

// Menu → cart: the agent proposes, the chef checks the amounts, then orders the cart as one order.
export function MenuPlanner({ onAction, onBusy, onAnnounce }: Props) {
  const [text, setText] = useState('')
  const [covers, setCovers] = useState('80')
  const [date, setDate] = useState(nextMonday)
  const [plan, setPlan] = useState<MenuRun | null>(null)
  const [planFor, setPlanFor] = useState({ covers: 0, date }) // what the shown plan was made for
  const [running, setRunning] = useState(false)
  const [ordering, setOrdering] = useState(false)
  const [ordered, setOrdered] = useState<OrderResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const n = Number(covers)
  const coversOk = Number.isInteger(n) && n >= 1 && n <= 2000

  useEffect(() => {
    if (!plan) return
    onAnnounce(`${STATUS.ASK_HUMAN}. A cart for ${planFor.covers} covers, ${formatCents(plan.cart_total_cents)}.`)
    heading.current?.focus()
  }, [plan, planFor.covers, onAnnounce])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setRunning(true)
    setError(null)
    setPlan(null)
    setOrdered(null)
    onAnnounce('Planning the cart…')
    try {
      setPlan(await planMenu({ menu_text: text.trim(), covers: n, requested_date: date }))
      setPlanFor({ covers: n, date })
    } catch (err) {
      setError(errorText(err))
    } finally {
      setRunning(false)
      onAction()
    }
  }

  async function orderCart() {
    if (!plan) return
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
      <form className="ask" onSubmit={submit}>
        <label className="ask-label" htmlFor="menu-text">
          What’s on the menu?
        </label>
        <textarea
          id="menu-text"
          className="ask-field"
          rows={3}
          maxLength={4000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={MENU_EXAMPLE}
          required
        />
        <div className="ask-row">
          <div className="ask-inputs">
            <label className="covers">
              Covers
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={2000}
                value={covers}
                onChange={(e) => setCovers(e.target.value)}
                required
              />
            </label>
            <label className="date-pick">
              Delivery <strong className="num">{formatDay(date)}</strong>
              <input
                type="date"
                aria-label="Delivery date"
                value={date}
                onChange={(e) => e.target.value && setDate(e.target.value)}
                onClick={(e) => e.currentTarget.showPicker?.()}
                required
              />
            </label>
          </div>
          <button type="submit" className="btn" disabled={running || ordering || !text.trim() || !coversOk}>
            {running ? 'Planning…' : 'Plan the cart'}
          </button>
        </div>
      </form>

      {running && (
        <div className="working">
          <p>{PLANNING}</p>
          <div className="working-bar" aria-hidden="true" />
        </div>
      )}
      {error && (
        <div className="problem" role="alert">
          <strong>That didn’t go through.</strong>
          {error}
        </div>
      )}

      {plan && ordered && (
        <RunResult
          key={ordered.audit_id}
          run={{
            request: { summary: `Menu for ${planFor.covers} covers`, items: plan.ingredients },
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

      {plan && !ordered && (
        <>
          <section className="answer" aria-label="Proposed cart">
            <p className="status warn">{STATUS.ASK_HUMAN}</p>
            <h2 ref={heading} tabIndex={-1} className="answer-text">
              A cart for {planFor.covers.toLocaleString('en-US')} covers, {formatCents(plan.cart_total_cents)}.
            </h2>
            <p className="answer-sub">
              The amounts per cover are the agent’s estimates. Check them below, then order. Delivery{' '}
              {formatDay(planFor.date)}, prices before VAT.
            </p>
            {plan.order_lines.length > 0 && (
              <div className="decide">
                <button type="button" className="btn" onClick={orderCart} disabled={ordering}>
                  {ordering ? 'Ordering…' : 'Order this cart'}
                </button>
              </div>
            )}
          </section>

          <section className="instead" aria-labelledby="menu-dishes">
            <h2 className="title" id="menu-dishes">
              The menu
            </h2>
            {plan.menu.dishes.map((d) => (
              <div key={d.name}>
                <h3 className="dish">{d.name}</h3>
                <ul>
                  {d.ingredients.map((i, k) => (
                    <li key={k} className="alt">
                      <div>
                        <p>{i.name}</p>
                        {i.assumption && <p className="quiet small">{i.assumption}</p>}
                      </div>
                      <p className="alt-side quiet">{i.per_cover != null ? `${amount(i.per_cover, i.unit)} per cover` : 'Amount unclear'}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
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
                  {chosen.length === 0 && <p className="option-why warn">Nothing on Valio’s list fits this yet.</p>}
                  {chosen.map((l) => (
                    <div key={l.product.id} className="split-row">
                      <span>{productName(l)}</span>
                      <span className="qty r">
                        {l.quantity?.quantity != null ? `${l.quantity.quantity.toLocaleString('en-US')} × ${unitName(l.quantity.sales_unit)}` : 'Amount unclear'}
                      </span>
                      <span className="r">{l.line_total_cents !== null ? formatCents(l.line_total_cents) : '—'}</span>
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
            <div className="split-total">
              <span>
                <strong>{formatCents(plan.cart_total_cents)}</strong> <span className="quiet">before VAT</span>
              </span>
            </div>
          </section>
        </>
      )}
    </>
  )
}
