import { useCopy } from './i18n'
import type { UrgentOption } from './types'

// "Need it sooner?": what a chef can do beyond the delivery the agent orders. Suggestions only, never an order.
// The backend writes English sentences; the facts inside them (hours, ready time, earliest date) are re-said in the
// chef's language, and anything that can't be read falls back to the backend's own sentence.
export function UrgentOptions({ options }: { options: UrgentOption[] }) {
  const c = useCopy()
  const t = c.UI.urgent
  return (
    <section className="instead urgent" aria-labelledby="urgent-title">
      <h2 className="title" id="urgent-title">
        {t.title}
      </h2>
      <p className="note">{t.note}</p>
      <ul>
        {options.map((o, i) => (
          <li key={i} className="alt urgent-row">
            <div>
              <p className="alt-rank">{label(o, t)}</p>
              {o.kind === 'walk_in' ? <WalkIn o={o} /> : <p>{body(o, c)}</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

type T = ReturnType<typeof useCopy>['UI']['urgent']

function label(o: UrgentOption, t: T): string {
  if (o.kind === 'walk_in') return t.walkIn
  if (o.kind === 'click_and_collect') return t.clickCollect
  if (o.kind === 'next_delivery') return t.nextDelivery
  return o.label
}

function body(o: UrgentOption, c: ReturnType<typeof useCopy>): string {
  if (o.kind === 'click_and_collect') return c.UI.urgent.ready(/around (\d\d:\d\d)/.exec(o.text)?.[1] ?? null)
  if (o.kind === 'next_delivery') {
    const m = /is (\d{4}-\d\d-\d\d)(?: if ordered before (\S+?))?\.?$/.exec(o.text)
    if (m) return c.UI.urgent.earliest(c.day(m[1]), m[2] ? safeDateTime(m[2], c) : null)
  }
  return o.text
}

const safeDateTime = (iso: string, c: ReturnType<typeof useCopy>) => (Number.isNaN(Date.parse(iso)) ? iso : c.dateTime(iso))

function WalkIn({ o }: { o: UrgentOption }) {
  const c = useCopy()
  const t = c.UI.urgent
  const name = o.label.split(': ').slice(1).join(': ') || o.label
  const h = o.hours ? /(\d\d:\d\d)–(\d\d:\d\d) \((open|closed) now\)/.exec(o.hours) : null
  return (
    <>
      <p>{name}</p>
      {o.address && <p className="quiet small">{o.address}</p>}
      {o.hours && <p className="quiet small num">{h ? t.hours(h[1], h[2], h[3] === 'open') : o.hours}</p>}
      {o.phone && (
        <p className="quiet small">
          {t.call(o.phone).split(o.phone)[0]}
          <a className="accent-text" href={`tel:${o.phone.replace(/\s/g, '')}`}>
            {o.phone}
          </a>
          {t.call(o.phone).split(o.phone)[1]}
        </p>
      )}
    </>
  )
}
