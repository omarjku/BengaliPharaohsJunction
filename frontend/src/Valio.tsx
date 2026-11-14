import { useEffect, useMemo, useState } from 'react'
import { getAdminAudit, verifySignature } from './api'
import { GroupLine, GroupSteps } from './AuditLog'
import { buyerLabel, errorText } from './format'
import { byDay, groupHistory, time } from './history'
import { useCopy } from './i18n'
import type { AdminFilter, AdminRow, AuditEntry, FrontDoorNote, SecurityEvent } from './types'

// Valio's side of the trail (J3: an audit trail for both buyer and Valio Aimo). Read-only, behind the Valio admin key:
// refused attempts first and set apart, then every kitchen's requests, grouped like the chef's History.
const SHOWS = ['all', 'confirmed', 'pending_approval', 'refused', 'rejected', 'ASK_HUMAN', 'DECLINE', 'security'] as const
type Show = (typeof SHOWS)[number]
type Entry = AuditEntry & { front_door?: FrontDoorNote }

const filterFor = (buyer: string, show: Show): AdminFilter => ({
  ...(buyer ? { buyer_id: buyer } : {}),
  ...(show === 'ASK_HUMAN' || show === 'DECLINE' ? { outcome: show } : {}),
  ...(show !== 'all' && show !== 'security' && show !== 'ASK_HUMAN' && show !== 'DECLINE' ? { status: show } : {}),
})
const buyerOf = (r: AdminRow) => (r.kind ? (r.buyer_id ?? r.caller_buyer_id ?? null) : r.input.request.buyer_id)

export function ValioView({ refreshKey, onForget }: { refreshKey: number; onForget: () => void }) {
  const c = useCopy()
  const t = c.UI.valio
  const [buyer, setBuyer] = useState('')
  const [show, setShow] = useState<Show>('all')
  const [rows, setRows] = useState<AdminRow[] | null>(null)
  const [buyers, setBuyers] = useState<string[]>([]) // every kitchen seen so far, so the filter keeps its options
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getAdminAudit(filterFor(buyer, show))
      .then((r) => {
        if (cancelled) return
        setRows(r)
        setBuyers((old) => [...new Set([...old, ...r.map(buyerOf).filter((b): b is string => !!b)])].sort())
      })
      .catch((e) => !cancelled && setError(errorText(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [buyer, show, refreshKey, manual])

  const security = useMemo(() => (rows ?? []).filter((r): r is SecurityEvent => r.kind === 'security_event').reverse(), [rows])
  const kitchens = useMemo(() => {
    const entries = show === 'security' ? [] : (rows ?? []).filter((r): r is Entry => !r.kind)
    const per = new Map<string, Entry[]>()
    for (const e of entries) per.set(e.input.request.buyer_id, [...(per.get(e.input.request.buyer_id) ?? []), e])
    // newest activity first
    return [...per].map(([id, list]) => ({ id, groups: groupHistory(list, c) })).sort((a, b) => b.groups[0].at.localeCompare(a.groups[0].at))
  }, [rows, show, c])
  const nothing = rows && !loading && !security.length && !kitchens.length

  return (
    <div>
      <div className="ask-row">
        <h1 className="title">{t.title}</h1>
        <button type="button" className="link" onClick={() => setManual((m) => m + 1)} disabled={loading}>
          {loading ? t.loading : t.refresh}
        </button>
      </div>
      <p className="note">{t.intro}</p>

      <div className="filters">
        <label className="filter">
          <span>{t.buyer}</span>
          <select value={buyer} onChange={(e) => setBuyer(e.target.value)}>
            <option value="">{t.allBuyers}</option>
            {buyers.map((b) => (
              <option key={b} value={b}>
                {buyerLabel(b)}
              </option>
            ))}
          </select>
        </label>
        <label className="filter">
          <span>{t.show}</span>
          <select value={show} onChange={(e) => setShow(e.target.value as Show)}>
            {SHOWS.map((s) => (
              <option key={s} value={s}>
                {t.shows[s]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <div className="problem" role="alert">
          <strong>{t.loadFailed}</strong>
          {error}
        </div>
      )}
      {nothing && <p className="note empty">{t.empty}</p>}

      {security.length > 0 && (show === 'all' || show === 'security') && (
        <section className="security" aria-labelledby="security-title">
          <h2 className="feed-day" id="security-title">
            {t.security}
          </h2>
          <p className="note small">{t.securityIntro}</p>
          <ol className="feed">
            {security.map((s) => (
              <li key={s.id} className="security-row">
                <span className="event-line">
                  <time className="event-time" dateTime={s.timestamp}>
                    {time(s.timestamp)}
                  </time>
                  <span className="event-what">
                    <span className="status-word bad">
                      <span className="dot bad" aria-hidden="true" />
                      {(t.event[s.event] ?? (() => t.unknownEvent(s.event)))(s.header ?? '')}
                    </span>
                    <span className="event-said">
                      {[buyerOf(s) && buyerLabel(buyerOf(s)!), t.route(s.route), c.longDay(s.timestamp)].filter(Boolean).join(' · ')}
                    </span>
                    {s.suppressed_before ? <span className="event-said">{t.suppressed(s.suppressed_before)}</span> : null}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {kitchens.map((k) => (
        <section key={k.id} className="kitchen" aria-labelledby={`kitchen-${k.id}`}>
          <h2 className="kitchen-title" id={`kitchen-${k.id}`}>
            {buyerLabel(k.id)} <span className="quiet small">{t.requests(k.groups.length)}</span>
          </h2>
          {byDay(k.groups, c).map(([label, groups]) => (
            <div key={label}>
              <h3 className="feed-day">{label}</h3>
              <ol className="feed">
                {groups.map((g) => (
                  <li key={g.key}>
                    <details className="event">
                      <summary>
                        <GroupLine g={g} />
                      </summary>
                      <GroupSteps g={g} extra={(e) => <Verify note={(e as Entry).front_door} />} />
                    </details>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </section>
      ))}

      <p className="note section-gap">
        <button type="button" className="link accent flush-link" onClick={onForget}>
          {t.forget}
        </button>
      </p>
    </div>
  )
}

// The front door signs what it decided (Ed25519); anyone can check it with POST /api/verify.
function Verify({ note }: { note?: FrontDoorNote }) {
  const t = useCopy().UI.valio
  const [state, setState] = useState<'idle' | 'busy' | 'valid' | 'invalid' | string>('idle')
  if (!note?.signed_statement || !note.signature) return null
  async function check() {
    setState('busy')
    try {
      setState((await verifySignature(note!.signed_statement!, note!.signature!)).valid ? 'valid' : 'invalid')
    } catch (e) {
      setState(errorText(e))
    }
  }
  if (state === 'valid') return <p className="status-word good small" role="status">{t.signed}</p>
  if (state === 'invalid') return <p className="status-word bad small" role="status">{t.notSigned}</p>
  return (
    <p>
      <button type="button" className="link accent verify" onClick={check} disabled={state === 'busy'}>
        {state === 'busy' ? t.verifying : t.verify}
      </button>
      {state !== 'idle' && state !== 'busy' && <span className="quiet"> {state}</span>}
    </p>
  )
}
