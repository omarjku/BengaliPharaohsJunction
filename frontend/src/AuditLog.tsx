import { useEffect, useState, type ReactNode } from 'react'
import { getAudit, getKeys, MOCK } from './api'
import { errorText } from './format'
import { byDay, groupHistory, time, type Group } from './history'
import { useCopy } from './i18n'
import type { AuditEntry } from './types'

export function AuditLog({ refreshKey, onEntries }: { refreshKey: number; onEntries: (entries: AuditEntry[]) => void }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)
  const approverKey = getKeys().approverKey
  const canRead = MOCK || Boolean(approverKey)
  const c = useCopy()
  const t = c.UI.history

  useEffect(() => {
    let cancelled = false
    setError(null)
    if (!canRead) {
      setEntries(null)
      setLoading(false)
      return
    }
    setLoading(true)
    getAudit()
      .then((e) => {
        if (cancelled) return
        setEntries(e) // oldest first, as the API sends it
        onEntries(e)
      })
      .catch((e) => !cancelled && setError(errorText(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [approverKey, canRead, refreshKey, manual, onEntries])

  const days = byDay(entries ? groupHistory(entries, c) : [], c)

  return (
    <div>
      <div className="ask-row">
        <h1 className="title">{t.title}</h1>
        <button type="button" className="link" onClick={() => setManual((m) => m + 1)} disabled={loading || !canRead}>
          {loading ? t.loading : t.refresh}
        </button>
      </div>
      <p className="note">{c.HISTORY_INTRO}</p>

      {!canRead && <p className="problem">{t.needKey}</p>}
      {error && (
        <div className="problem" role="alert">
          <strong>{t.loadFailed}</strong>
          {error}
        </div>
      )}
      {entries && entries.length === 0 && <p className="note empty">{t.empty}</p>}

      {days.map(([label, groups]) => (
        <section key={label} aria-label={label}>
          <h2 className="feed-day">{label}</h2>
          <ol className="feed">
            {groups.map((g) => (
              <li key={g.key}>
                <details className="event">
                  <summary>
                    <GroupLine g={g} />
                  </summary>
                  <GroupSteps g={g} />
                </details>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}

// The steps inside one request: who did what, the reasons, the confidence. `extra` adds to a step (Valio's verify).
export function GroupSteps({ g, extra }: { g: Group; extra?: (e: AuditEntry) => ReactNode }) {
  const c = useCopy()
  return (
    <ol className="event-body">
      {g.steps.map(({ e, what }) => (
        <li key={e.id} className="step">
          <p>
            <time className="event-time" dateTime={e.timestamp}>
              {time(e.timestamp)}
            </time>{' '}
            {what}
          </p>
          {e.decision.reasons
            // a sign-off repeats the order's reasons; a rules change lists what changed
            .filter((r) => (e.actor.endsWith(':mandate') ? true : !e.actor.startsWith('human:') && r.severity !== 'INFO'))
            .map((r, i) => (
              <p key={i} className="quiet">
                {c.humanize(r.message)}
              </p>
            ))}
          {e.decision.confidence != null && <p className="quiet num">{c.matched(e.decision.confidence)}</p>}
          {extra?.(e)}
        </li>
      ))}
    </ol>
  )
}

export function GroupLine({ g }: { g: Group }) {
  return (
    <span className="event-line">
      <time className="event-time" dateTime={g.at}>
        {time(g.at)}
      </time>
      <span className="event-what">
        {g.title}
        <span className={`event-said status-word ${g.tone}`}>
          <span className={`dot ${g.tone}`} aria-hidden="true" />
          {g.outcome}
        </span>
      </span>
    </span>
  )
}

// The last few requests, for the empty order screen: does anything need me?
export function Recent({ groups, onOpen }: { groups: Group[]; onOpen: () => void }) {
  const t = useCopy().UI.history
  if (!groups.length) return null
  return (
    <section className="recent" aria-labelledby="recent-title">
      <div className="ask-row">
        <h2 className="feed-day" id="recent-title">
          {t.recently}
        </h2>
        <button type="button" className="link" onClick={onOpen}>
          {t.all}
        </button>
      </div>
      <ol className="feed">
        {groups.map((g) => (
          <li key={g.key} className="recent-row">
            <GroupLine g={g} />
          </li>
        ))}
      </ol>
    </section>
  )
}
