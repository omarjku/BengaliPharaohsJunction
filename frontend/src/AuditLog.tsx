import { useEffect, useState } from 'react'
import { getAudit, getKeys, MOCK } from './api'
import { errorText, formatDateTime, outcomeView } from './format'
import type { AuditEntry } from './types'

export function AuditLog({ refreshKey }: { refreshKey: number }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)
  const approverKey = getKeys().approverKey
  const canRead = MOCK || Boolean(approverKey)

  useEffect(() => {
    let cancelled = false
    if (!canRead) {
      setEntries(null)
      setLoading(false)
      setError(null)
      return () => {
        cancelled = true
      }
    }
    setEntries(null)
    setLoading(true)
    setError(null)
    getAudit()
      .then((e) => !cancelled && setEntries([...e].reverse())) // API is oldest first
      .catch((e) => !cancelled && setError(errorText(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [approverKey, canRead, refreshKey, manual])

  return (
    <section className="card" aria-labelledby="audit-title">
      <div className="audit-head">
        <h2 id="audit-title">Audit log</h2>
        <button type="button" className="secondary" onClick={() => setManual((m) => m + 1)} disabled={loading || !canRead}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      {!canRead && <p className="muted">Enter the approver key in Keys to see the audit log.</p>}
      {canRead && entries && entries.length > 0 && (
        <p className="muted">Every decision for buyer {entries[0].input.request.buyer_id}, newest first.</p>
      )}
      {error && (
        <p className="error" role="alert">
          Couldn’t load the audit log: {error}
        </p>
      )}
      {entries && entries.length === 0 && <p className="muted">No entries yet.</p>}
      {entries && entries.length > 0 && (
        <ol className="audit">
          {entries.map((e) => (
            <li key={e.id}>
              <p>
                <Chip entry={e} />{' '}
                <time dateTime={e.timestamp}>{formatDateTime(e.timestamp)}</time>{' '}
                <span className="muted">· {actorLabel(e.actor)}</span>
              </p>
              <p>{e.input.request.text}</p>
              {e.decision.reasons.length > 0 && (
                <ul className="muted">
                  {e.decision.reasons.map((r, i) => (
                    <li key={i}>{r.message}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

// A human sign-off shows what the human did; otherwise the decision's outcome.
function Chip({ entry }: { entry: AuditEntry }) {
  const action = /:(approve|reject)$/.exec(entry.actor)?.[1]
  if (entry.actor.startsWith('human:') && action)
    return <span className={`badge ${action === 'approve' ? 'auto' : 'decline'}`}>{action === 'approve' ? 'Approved' : 'Rejected'}</span>
  return <span className={`badge ${entry.decision.outcome.toLowerCase()}`}>{outcomeView(entry.decision.outcome)[1]}</span>
}

// actor is 'buyer_agent', 'valio_front_door' or 'human:<name>:approve|reject'.
function actorLabel(actor: string): string {
  const human = /^human:(.+?)(?::(approve|reject))?$/.exec(actor) // names may contain ':'
  if (human) return human[2] ? `${human[2] === 'approve' ? 'approved' : 'rejected'} by ${human[1]}` : human[1]
  return { buyer_agent: 'buyer agent', valio_front_door: 'Valio front door' }[actor] ?? actor
}
