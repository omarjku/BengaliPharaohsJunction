import { useEffect, useState } from 'react'
import { getAudit } from './api'
import { errorText, formatDateTime } from './format'
import type { AuditEntry } from './types'

export function AuditLog({ buyerId, refreshKey }: { buyerId: string; refreshKey: number }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getAudit(buyerId)
      .then((e) => !cancelled && setEntries(e))
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
            <li key={e.audit_id}>
              <p>
                <span className={`badge ${e.outcome.toLowerCase()}`}>{e.outcome.replace(/_/g, ' ')}</span>{' '}
                <time dateTime={e.at}>{formatDateTime(e.at)}</time>
              </p>
              <p>{e.summary}</p>
              {e.reasons.length > 0 && (
                <ul className="muted">
                  {e.reasons.map((r, i) => (
                    <li key={i}>{r.text}</li>
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
