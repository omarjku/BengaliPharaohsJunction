import { useEffect, useState } from 'react'
import { getAudit } from './api'
import { errorText, formatDateTime, outcomeView } from './format'
import type { AuditEntry } from './types'

export function AuditLog({ buyerId, refreshKey }: { buyerId: string; refreshKey: number }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)

  useEffect(() => {
    let cancelled = false
    setEntries(null)
    setLoading(true)
    setError(null)
    getAudit(buyerId)
      .then((e) => !cancelled && setEntries([...e].reverse())) // API is oldest first
      .catch((e) => !cancelled && setError(errorText(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [buyerId, refreshKey, manual])

  return (
    <section className="card" aria-labelledby="audit-title">
      <div className="audit-head">
        <h2 id="audit-title">Audit log</h2>
        <button type="button" className="secondary" onClick={() => setManual((m) => m + 1)} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <p className="muted">Every decision for buyer {buyerId}, newest first.</p>
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
                <span className={`badge ${e.decision.outcome.toLowerCase()}`}>{outcomeView(e.decision.outcome)[1]}</span>{' '}
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

// actor is 'buyer_agent', 'valio_front_door' or 'human:<name>:approve|reject'.
function actorLabel(actor: string): string {
  const [kind, name, action] = actor.split(':')
  if (kind === 'human' && name) return action === 'reject' ? `rejected by ${name}` : action === 'approve' ? `approved by ${name}` : name
  return { buyer_agent: 'buyer agent', valio_front_door: 'Valio front door' }[kind] ?? actor
}
