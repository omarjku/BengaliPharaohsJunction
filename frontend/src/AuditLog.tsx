import { useEffect, useState } from 'react'
import { getAudit, getKeys, MOCK } from './api'
import { errorText, formatConfidence, outcomeView, type Tone } from './format'
import type { AuditEntry } from './types'

type Category = 'ordered' | 'ask' | 'refused'
type Filter = 'all' | Category
const FILTERS: [Filter, string][] = [
  ['all', 'All'],
  ['ordered', 'Ordered'],
  ['ask', 'Needs your OK'],
  ['refused', 'Refused'],
]
const ICON: Record<Tone, string> = { good: '✓', warn: '!', bad: '✕', neutral: '–' }
const HELSINKI = 'Europe/Helsinki'
const time = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: HELSINKI })
const day = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: HELSINKI })

// What an entry means for the chef: a human sign-off shows what the human did; otherwise the decision's outcome.
function view(e: AuditEntry): { cat: Category; tone: Tone; label: string } {
  const action = e.actor.startsWith('human:') ? /:(approve|reject)$/.exec(e.actor)?.[1] : undefined
  if (action === 'approve') return { cat: 'ordered', tone: 'good', label: 'Approved' }
  if (action === 'reject') return { cat: 'refused', tone: 'bad', label: 'Rejected' }
  const [tone, label] = outcomeView(e.decision.outcome)
  return { cat: e.decision.outcome === 'AUTO' ? 'ordered' : e.decision.outcome === 'DECLINE' ? 'refused' : 'ask', tone, label }
}

// actor is 'buyer_agent', 'valio_front_door' or 'human:<name>:approve|reject' (names may contain ':').
function actorLabel(actor: string): string {
  const human = /^human:(.+?)(?::(approve|reject))?$/.exec(actor)
  if (human) return human[1]
  return { buyer_agent: 'Buyer agent', valio_front_door: 'Valio front door' }[actor] ?? actor
}

// Gemini's own words only appear in the audit as a LOW_CONFIDENCE reason; otherwise just the number.
const lowConfidence = (e: AuditEntry) => e.decision.reasons.filter((r) => r.code === 'LOW_CONFIDENCE')
const GeminiPill = ({ value }: { value: number }) => (
  <span className={`pill tone-${value >= 0.8 ? 'good' : 'warn'}`}>Gemini {formatConfidence(value)}</span>
)

export function AuditLog({ refreshKey, onBuyer }: { refreshKey: number; onBuyer: (buyer: string | null) => void }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)
  const [filter, setFilter] = useState<Filter>('all')
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

  const views = (entries ?? []).map((e) => ({ e, ...view(e) }))
  const count = (f: Filter) => views.filter((v) => f === 'all' || v.cat === f).length
  const shown = views.filter((v) => filter === 'all' || v.cat === filter)
  const confidences = (entries ?? []).filter((e) => e.actor === 'buyer_agent' && e.decision.confidence != null)
  const avgConfidence = confidences.length
    ? confidences.reduce((a, e) => a + (e.decision.confidence ?? 0), 0) / confidences.length
    : null

  return (
    <div className="stack">
      <div className="card-head">
        <div>
          <h1 className="card-title">Audit log</h1>
          <p className="small muted">Every decision the agent, Valio’s front door and you made for this buyer, newest first.</p>
        </div>
        <button type="button" className="btn secondary" onClick={() => setManual((m) => m + 1)} disabled={loading || !canRead}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {!canRead && <p className="notice">Enter the approver key in Keys to see the audit log.</p>}
      {error && (
        <p className="error" role="alert">
          Couldn’t load the audit log: {error}
        </p>
      )}

      {entries && entries.length > 0 && (
        <>
          <div className="filters" role="group" aria-label="Filter by outcome">
            {FILTERS.map(([f, label]) => (
              <button key={f} type="button" className="filter" aria-pressed={filter === f} onClick={() => setFilter(f)}>
                {label}
                <span className="count">{count(f)}</span>
              </button>
            ))}
          </div>

          <dl className="card summary">
            <div>
              <dt className="label">Decisions</dt>
              <dd className="value">{entries.length}</dd>
            </div>
            <div>
              <dt className="label">Ordered</dt>
              <dd className="value">{count('ordered')}</dd>
            </div>
            <div>
              <dt className="label">Signed off by a human</dt>
              <dd className="value">{entries.filter((e) => e.actor.startsWith('human:')).length}</dd>
            </div>
            <div>
              <dt className="label">Avg Gemini confidence</dt>
              <dd className="value">{avgConfidence !== null ? formatConfidence(avgConfidence) : '—'}</dd>
            </div>
          </dl>
        </>
      )}

      {entries && shown.length === 0 && <p className="muted">{entries.length ? 'No entries match this filter.' : 'No entries yet.'}</p>}
      {shown.length > 0 && (
        <ol className="timeline">
          {shown.map(({ e, tone, label }) => (
            <li key={e.id} className="tl-item">
              <p className="tl-time">
                <time dateTime={e.timestamp}>
                  <strong>{time.format(new Date(e.timestamp))}</strong>
                  <br />
                  <span className="muted">{day.format(new Date(e.timestamp))}</span>
                </time>
              </p>
              <span className={`tl-dot ${tone}`} aria-hidden="true">
                {ICON[tone]}
              </span>
              <article className={`card tl-card ${tone}`}>
                <div className="tl-head">
                  <span className="tl-tags">
                    <span className="pill tone-neutral">{actorLabel(e.actor)}</span>
                    {e.decision.confidence != null && !lowConfidence(e).length && <GeminiPill value={e.decision.confidence} />}
                  </span>
                  <span className={`pill tone-${tone}`}>
                    <span aria-hidden="true">{ICON[tone]}</span> {label}
                  </span>
                </div>
                <p className="tl-title">{e.input.request.text}</p>
                {e.decision.reasons[0] && e.decision.reasons[0].code !== 'LOW_CONFIDENCE' && (
                  <p className="small">{e.decision.reasons[0].message}</p>
                )}
                {e.decision.confidence != null && lowConfidence(e).length > 0 && (
                  <div className="gemini">
                    <p className="gemini-head">
                      Gemini reasoning
                      <GeminiPill value={e.decision.confidence} />
                    </p>
                    {lowConfidence(e).map((r, i) => (
                      <p key={i}>{r.message}</p>
                    ))}
                  </div>
                )}
                {e.decision.reasons.length > 1 && (
                  <details>
                    <summary>All {e.decision.reasons.length} reasons</summary>
                    <ul className="stack-sm small">
                      {e.decision.reasons.map((r, i) => (
                        <li key={i}>
                          {r.message}
                          {r.suggested_fix && <span className="muted"> {r.suggested_fix}</span>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </article>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
