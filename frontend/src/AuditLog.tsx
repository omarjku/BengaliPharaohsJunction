import { useEffect, useState } from 'react'
import { getAudit, getKeys, MOCK } from './api'
import { confidenceSentence } from './copy'
import { errorText, formatConfidence, type Tone } from './format'
import type { AuditEntry } from './types'

const HELSINKI = 'Europe/Helsinki'
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: HELSINKI })
const dayKey = new Intl.DateTimeFormat('en-CA', { timeZone: HELSINKI }) // YYYY-MM-DD in Helsinki
const dayName = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: HELSINKI })

function dayLabel(iso: string, now = new Date()): string {
  const d = dayKey.format(new Date(iso))
  if (d === dayKey.format(now)) return 'Today'
  if (d === dayKey.format(new Date(now.getTime() - 86_400_000))) return 'Yesterday'
  return dayName.format(new Date(iso))
}

// One line in plain words: who did what. Status colour comes only with these words.
function describe(e: AuditEntry): { tone: Tone; what: string } {
  const human = /^human:(.+?)(?::(approve|reject))?$/.exec(e.actor)
  if (human?.[2] === 'approve') return { tone: 'good', what: `${human[1]} approved the order` }
  if (human?.[2] === 'reject') return { tone: 'bad', what: `${human[1]} rejected the order` }
  const o = e.decision.outcome
  const tone: Tone = o === 'AUTO' ? 'good' : o === 'DECLINE' ? 'bad' : 'warn'
  if (e.actor === 'buyer_agent')
    return { tone, what: o === 'AUTO' ? 'The agent sent the order to Valio' : o === 'DECLINE' ? 'The agent didn’t order' : 'The agent asked for your OK' }
  if (e.actor === 'valio_front_door')
    return { tone, what: o === 'AUTO' ? 'Valio confirmed the order' : o === 'DECLINE' ? 'Valio refused the order' : 'Valio held the order for your OK' }
  return { tone, what: human?.[1] ?? e.actor }
}

// What was asked, without the system prefix the front door adds.
const said = (e: AuditEntry) => e.input.request.text.replace(/^Order via Valio front door:\s*/, '')

export function AuditLog({ refreshKey, onBuyer }: { refreshKey: number; onBuyer: (buyer: string | null) => void }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)
  const approverKey = getKeys().approverKey
  const canRead = MOCK || Boolean(approverKey)

  useEffect(() => {
    let cancelled = false
    setEntries(null)
    setError(null)
    if (!canRead) {
      setLoading(false)
      return
    }
    setLoading(true)
    getAudit()
      .then((e) => {
        if (cancelled) return
        setEntries([...e].reverse()) // API is oldest first
        onBuyer(e[0]?.input.request.buyer_id ?? null)
      })
      .catch((e) => !cancelled && setError(errorText(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [approverKey, canRead, refreshKey, manual, onBuyer])

  const days: [string, AuditEntry[]][] = []
  for (const e of entries ?? []) {
    const label = dayLabel(e.timestamp)
    const last = days[days.length - 1]
    if (last?.[0] === label) last[1].push(e)
    else days.push([label, [e]])
  }

  return (
    <div>
      <div className="ask-row">
        <h1 className="title">History</h1>
        <button type="button" className="link" onClick={() => setManual((m) => m + 1)} disabled={loading || !canRead}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <p className="note">Everything the agent, Valio and you decided, newest first.</p>

      {!canRead && <p className="problem">Add your approver key under Keys to see the history.</p>}
      {error && (
        <div className="problem" role="alert">
          <strong>Couldn’t load the history.</strong>
          {error}
        </div>
      )}
      {entries && entries.length === 0 && <p className="note empty">Nothing yet. Your first order will show up here.</p>}

      {days.map(([label, list]) => (
        <section key={label} aria-label={label}>
          <h2 className="feed-day">{label}</h2>
          <ol className="feed">
            {list.map((e) => {
              const { tone, what } = describe(e)
              return (
                <li key={e.id}>
                  <details className="event">
                    <summary>
                      <span className="event-line">
                        <time className="event-time" dateTime={e.timestamp}>
                          {clock.format(new Date(e.timestamp))}
                        </time>
                        <span className="event-what">
                          <span className={`dot ${tone}`} aria-hidden="true" />
                          {what}
                          <span className="event-said">{said(e)}</span>
                        </span>
                      </span>
                    </summary>
                    <div className="event-body">
                      {e.decision.reasons.map((r, i) => (
                        <p key={i}>
                          {r.message}
                          {r.suggested_fix && <> {r.suggested_fix}</>}
                        </p>
                      ))}
                      {e.decision.confidence != null && (
                        <p className="num">
                          Gemini: {confidenceSentence(e.decision.confidence).toLowerCase()} · {formatConfidence(e.decision.confidence)}
                        </p>
                      )}
                    </div>
                  </details>
                </li>
              )
            })}
          </ol>
        </section>
      ))}
    </div>
  )
}
