import { useEffect, useRef, useState, type FormEvent } from 'react'
import { getHealth, getKeys, MOCK, runAgent, setKeys } from './api'
import { AuditLog } from './AuditLog'
import { errorText, nextMonday } from './format'
import { RunResult } from './RunResult'
import type { AgentRun, Health } from './types'

const EXAMPLE = 'We need 1000 L of lactose-free milk delivered by Monday.'
type View = 'console' | 'audit'

// "lapland-kitchen" -> "Lapland kitchen": the buyer id is all the API tells us about the buyer.
const buyerLabel = (id: string) => id.replace(/[-_.]+/g, ' ').replace(/^./, (c) => c.toUpperCase())

export default function App() {
  const [view, setView] = useState<View>('console')
  const [keys, setKeyDraft] = useState(getKeys) // the modal's inputs; applied on Save
  const [savedKeys, setSavedKeys] = useState(getKeys)
  const keysDialog = useRef<HTMLDialogElement>(null)
  const [buyer, setBuyer] = useState<string | null>(null) // from the audit trail the approver key can read
  const [text, setText] = useState(EXAMPLE)
  const [date, setDate] = useState(nextMonday)
  const [runDate, setRunDate] = useState(date) // the date the shown run was for (split orders reuse it)
  const [run, setRun] = useState<AgentRun | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  const refreshAudit = () => setAuditKey((k) => k + 1)

  function openKeys() {
    setKeyDraft(getKeys())
    keysDialog.current?.showModal()
  }

  function saveKeys(e: FormEvent) {
    e.preventDefault()
    setKeys(keys)
    setSavedKeys(getKeys())
    keysDialog.current?.close()
    refreshAudit()
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setRunning(true)
    setAnnounce('Asking the agent…')
    setError(null)
    setRun(null)
    setRunDate(date)
    try {
      setRun(await runAgent({ text: text.trim(), requested_date: date }))
    } catch (err) {
      setError(errorText(err))
      setAnnounce('')
    } finally {
      setRunning(false)
      refreshAudit()
    }
  }

  const missingKeys = !MOCK && (!savedKeys.agentKey || !savedKeys.approverKey)

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <p className="wordmark">
            Front Door<span>for Valio Aimo</span>
          </p>
          <nav className="tabs" role="tablist" aria-label="Views">
            {(['console', 'audit'] as const).map((v) => (
              <button
                key={v}
                type="button"
                role="tab"
                id={`tab-${v}`}
                aria-controls={`view-${v}`}
                aria-selected={view === v}
                className="tab"
                onClick={() => setView(v)}
              >
                {v === 'console' ? 'Agent console' : 'Audit log'}
              </button>
            ))}
          </nav>
          <div className="topbar-end">
            <div className="who">
              <strong>{buyer ? buyerLabel(buyer) : MOCK ? 'Mock buyer' : 'Buyer from your keys'}</strong>
              <BackendStatus />
            </div>
            <button type="button" className="btn secondary" onClick={openKeys}>
              Keys
            </button>
          </div>
        </div>
      </header>

      <dialog ref={keysDialog} className="modal" aria-labelledby="keys-title">
        <form className="stack" onSubmit={saveKeys}>
          <h2 id="keys-title" className="card-title">
            Keys
          </h2>
          <div className="field">
            <label htmlFor="agent-key">Agent key</label>
            <p className="small muted" id="agent-key-help">
              Lets the AI agent place orders for your kitchen.
            </p>
            <input
              id="agent-key"
              type="password"
              autoComplete="off"
              aria-describedby="agent-key-help"
              value={keys.agentKey}
              onChange={(e) => setKeyDraft({ ...keys, agentKey: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="approver-key">Approver key</label>
            <p className="small muted" id="approver-key-help">
              Yours alone: approves or rejects orders and reads the audit log.
            </p>
            <input
              id="approver-key"
              type="password"
              autoComplete="off"
              aria-describedby="approver-key-help"
              value={keys.approverKey}
              onChange={(e) => setKeyDraft({ ...keys, approverKey: e.target.value })}
            />
          </div>
          <div className="actions">
            <button type="submit" className="btn">
              Save keys
            </button>
            <button type="button" className="btn secondary" onClick={() => keysDialog.current?.close()}>
              Cancel
            </button>
          </div>
        </form>
      </dialog>

      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      <main>
        {MOCK && (
          <p className="notice">
            Mock mode: no backend calls. “1000” needs your OK, “cream” or “tomorrow” is refused with substitutes,
            “stock” proposes a split order, “error” fails, anything else is ordered.
          </p>
        )}
        {missingKeys && (
          <p className="notice">
            Add your agent key and approver key to start.{' '}
            <button type="button" className="btn secondary" onClick={openKeys}>
              Open keys
            </button>
          </p>
        )}

        <section id="view-console" role="tabpanel" aria-labelledby="tab-console" hidden={view !== 'console'} className="stack">
          <form className="card stack" onSubmit={submit}>
            <h1 className="card-title">What do you need?</h1>
            <div className="field">
              <label htmlFor="text">Request</label>
              <textarea
                id="text"
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="1000 L lactose-free milk for Monday"
                required
              />
            </div>
            <div className="form-row">
              <div className="field">
                <label htmlFor="date">Delivery date</label>
                <input id="date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
              </div>
              <div>
                <button type="submit" className="btn" disabled={running || deciding || !text.trim()}>
                  {running ? 'Asking the agent…' : 'Ask the agent'}
                </button>
              </div>
            </div>
            {running && <p className="small muted">Searching the catalogue and checking price and availability…</p>}
          </form>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {run && (
            <RunResult
              key={run.audit_id}
              run={run}
              requestedDate={runDate}
              onAction={refreshAudit}
              onBusy={setDeciding}
              onAnnounce={setAnnounce}
            />
          )}
        </section>

        <section id="view-audit" role="tabpanel" aria-labelledby="tab-audit" hidden={view !== 'audit'}>
          <AuditLog refreshKey={auditKey} onBuyer={setBuyer} />
        </section>
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

  if (error) return <span className="status bad">Backend offline</span>
  if (!health) return <span className="status">Checking backend…</span>
  const cat = health.catalogue
  const catText = cat.ready ? `${cat.products.toLocaleString('en-US')} products` : cat.error ? 'catalogue failed' : 'catalogue loading'
  return (
    <span className={`status ${cat.ready ? 'good' : 'warn'}`} title={error ?? undefined}>
      {MOCK ? 'Mock data' : 'Connected'} · {catText}
    </span>
  )
}
