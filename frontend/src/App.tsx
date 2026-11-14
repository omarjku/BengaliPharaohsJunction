import { useEffect, useState, type FormEvent } from 'react'
import { getHealth, getKeys, MOCK, runAgent, setKeys } from './api'
import { AuditLog } from './AuditLog'
import { errorText, nextMonday } from './format'
import { RunResult } from './RunResult'
import type { AgentRun, Health } from './types'

const EXAMPLE = 'We need 1000 L of lactose-free milk delivered by Monday.'
const DEFAULT_BUYER = 'lapland-kitchen' // the buyer with a server-side mandate; the agent key decides once /api/agent/run checks it
export default function App() {
  const [keys, setKeyDraft] = useState(getKeys) // the inputs; applied on Save
  const [text, setText] = useState(EXAMPLE)
  const [date, setDate] = useState(nextMonday)
  const [buyerId, setBuyerId] = useState(DEFAULT_BUYER)
  const [run, setRun] = useState<AgentRun | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  const refreshAudit = () => setAuditKey((k) => k + 1)

  function saveKeys(e: FormEvent) {
    e.preventDefault()
    setKeys(keys)
    setKeyDraft(getKeys())
    refreshAudit()
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const buyer = buyerId.trim()
    setRunning(true)
    setAnnounce('Asking the agent…')
    setError(null)
    setRun(null)
    try {
      setRun(await runAgent({ text: text.trim(), requested_date: date, buyer_id: buyer }))
    } catch (err) {
      setError(errorText(err))
      setAnnounce('')
    } finally {
      setRunning(false)
      refreshAudit()
    }
  }

  return (
    <>
      <header className="topbar">
        <h1>Valio Aimo Front Door</h1>
        <BackendStatus />
      </header>
      <main>
        {MOCK && (
          <p className="notice">
            Mock mode: no backend calls. Requests with “1000” need your OK, “cream” or “tomorrow” are refused at
            the front door, “error” fails, anything else is ordered.
          </p>
        )}

        <form className="card" aria-labelledby="keys-title" onSubmit={saveKeys}>
          <h2 id="keys-title">Keys</h2>
          <div className="row">
            <div>
              <label htmlFor="agent-key">Agent key</label>
              <input
                id="agent-key"
                type="password"
                autoComplete="off"
                value={keys.agentKey}
                onChange={(e) => setKeyDraft({ ...keys, agentKey: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="approver-key">Approver key</label>
              <input
                id="approver-key"
                type="password"
                autoComplete="off"
                value={keys.approverKey}
                onChange={(e) => setKeyDraft({ ...keys, approverKey: e.target.value })}
              />
            </div>
          </div>
          <button type="submit" className="secondary">
            Save keys
          </button>
        </form>

        <form className="card" onSubmit={submit}>
          <h2>What do you need?</h2>
          <label htmlFor="text">Request</label>
          <textarea id="text" rows={3} value={text} onChange={(e) => setText(e.target.value)} required />
          <div className="row">
            <div>
              <label htmlFor="date">Delivery date</label>
              <input id="date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
            </div>
            <div>
              <label htmlFor="buyer">Buyer ID</label>
              <input id="buyer" value={buyerId} onChange={(e) => setBuyerId(e.target.value)} required />
            </div>
          </div>
          <button type="submit" disabled={running || deciding || !text.trim() || !buyerId.trim()}>
            {running ? 'Asking the agent…' : 'Ask the agent'}
          </button>
        </form>

        <p className="sr-only" aria-live="polite">
          {announce}
        </p>
        {running && <p className="muted">Searching the catalogue and checking price and availability…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {run && (
          <RunResult key={run.audit_id} run={run} onAction={refreshAudit} onBusy={setDeciding} onAnnounce={setAnnounce} />
        )}

        <AuditLog refreshKey={auditKey} />
      </main>
    </>
  )
}

function BackendStatus() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getHealth().then(
      (h) => !cancelled && (setHealth(h), setError(null)),
      (e) => !cancelled && setError(errorText(e)),
    )
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <p className="status bad">Backend offline: {error}</p>
  if (!health) return <p className="status">Checking backend…</p>
  const cat = health.catalogue
  const catText = cat.ready ? `catalogue ready (${cat.products.toLocaleString('en-US')} products)` : cat.error ? 'catalogue failed to load' : 'catalogue loading…'
  return (
    <p className={`status ${cat.ready ? 'good' : 'warn'}`}>
      {MOCK ? 'Mock data' : `Backend ${health.status}`} · {catText}
    </p>
  )
}
