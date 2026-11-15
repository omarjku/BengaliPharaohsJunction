import { useEffect, useRef, type ReactNode } from 'react'
import { useCopy } from './i18n'
import type { Tone } from './format'
import './Cart.css'

export type CartFact = { label: string; tone?: Tone }
export type CartWhy = { label: string; value: string; tone?: Tone }
export type CartLine = {
  id: string
  name: string
  pack: string
  unitPrice: string
  total: string
  facts: CartFact[]
  confidence?: string | null
  why: CartWhy[]
  detail?: ReactNode
}

type CartProps = {
  id: string
  status: string
  tone: Tone
  delivery: string
  reason?: string | null
  lines: CartLine[]
  total: string
  body?: ReactNode
  footer?: ReactNode
  belowFooter?: ReactNode
  autoScroll?: boolean
  ariaLabel?: string
}

export function Cart({ id, status, tone, delivery, reason, lines, total, body, footer, belowFooter, autoScroll = false, ariaLabel }: CartProps) {
  const c = useCopy()
  const t = c.UI.result
  const root = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!autoScroll || !root.current) return
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    root.current.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
  }, [autoScroll, id])

  return (
    <section ref={root} id={id} className={`answer cart cart-${tone}`} aria-label={ariaLabel ?? status}>
      <header className="cart-header">
        <span className={`status cart-status ${tone}`}>{status}</span>
        <span className="cart-delivery num">
          {t.delivery} {delivery}
        </span>
        {reason && <p className="cart-reason">{reason}</p>}
      </header>

      <ul className="cart-lines">
        {lines.map((line) => (
          <li key={line.id} className="cart-line">
            <div className="cart-line-top">
              <div className="cart-product">
                <p className="cart-product-name">{line.name}</p>
                <p className="cart-pack num">{line.pack}</p>
              </div>
              <dl className="cart-price num">
                <div>
                  <dt>{t.colPrice}</dt>
                  <dd>{line.unitPrice}</dd>
                </div>
                <div>
                  <dt>{t.colTotal}</dt>
                  <dd className="cart-line-total">{line.total}</dd>
                </div>
              </dl>
            </div>
            {(line.facts.length > 0 || line.confidence) && (
              <div className="cart-facts" aria-label={line.name}>
                {line.facts.map((fact, i) => (
                  <span key={`${fact.label}-${i}`} className={`cart-fact${fact.tone ? ` ${fact.tone}` : ''}`}>
                    {fact.label}
                  </span>
                ))}
                {line.confidence && <span className="cart-confidence num">{line.confidence}</span>}
              </div>
            )}
            <details className="cart-why">
              <summary>{t.why(line.name)}</summary>
              <dl className="cart-why-list">
                {line.why.map((row) => (
                  <div key={row.label} className={row.tone ? `cart-why-${row.tone}` : undefined}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
              {line.detail && <div className="cart-line-detail">{line.detail}</div>}
            </details>
          </li>
        ))}
      </ul>

      {body && <div className="cart-body">{body}</div>}
      <footer className="cart-footer">
        <p className="cart-total num">
          <span>{t.exclVat}</span>
          <strong>{total}</strong>
        </p>
        {footer && <div className="cart-actions">{footer}</div>}
      </footer>
      {belowFooter && <div className="cart-extra">{belowFooter}</div>}
    </section>
  )
}

export function CartDock({ status, tone, items, total, delivery, onOpen }: {
  status: string
  tone: Tone
  items: number
  total: string
  delivery: string
  onOpen: () => void
}) {
  const c = useCopy()
  return (
    <button
      type="button"
      className="cart-dock"
      onClick={onOpen}
      aria-label={`${status}. ${c.UI.result.products(items)}. ${total}. ${c.UI.result.delivery} ${delivery}.`}
    >
      <span className={`cart-dock-dot ${tone}`} aria-hidden="true" />
      <span className="cart-dock-items">{c.UI.result.products(items)}</span>
      <strong className="cart-dock-total num">{total}</strong>
      <span className="cart-dock-delivery num">{delivery}</span>
    </button>
  )
}
