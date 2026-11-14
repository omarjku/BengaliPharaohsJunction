import { useEffect, useRef, useState, type FormEvent } from 'react'
import { getHealth, getKeys, MOCK, runAgent, setKeys, type ApiKeys } from './api'
import { AuditLog } from './AuditLog'
import { MenuPlanner } from './Menu'
import { Rules } from './Rules'
import { EXAMPLE, RUNNING } from './copy'
import { errorText, formatDay, nextMonday } from './format'
import { RunResult } from './RunResult'
import type { AgentRun } from './types'

type View = 'order' | 'menu' | 'rules' | 'history'

// "lapland-kitchen" -> "Lapland kitchen": the buyer id is all the API tells us about the buyer.
const buyerLabel = (id: string) => id.replace(/[-_.]+/g, ' ').replace(/^./, (c) => c.toUpperCase())

export default function App() {
  const [view, setView] = useState<View>('order')
  const [savedKeys, setSavedKeys] = useState(getKeys)
  const keysDialog = useRef<HTMLDialogElement>(null)
  const [buyer, setBuyer] = useState<string | null>(null) // from the history the approver key can read
  const [text, setText] = useState('')
  const [date, setDate] = useState(nextMonday)
  const [runDate, setRunDate] = useState(date) // the date the shown run was for (split orders reuse it)
  const [run, setRun] = useState<AgentRun | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  const refreshAudit = () => setAuditKey((k) => k + 1)
  const offline = useBackendDown()

  const needsSetup = !MOCK && (!savedKeys.agentKey || !savedKeys.approverKey)

  function keysSaved() {
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

  return (
    <>
      <header className="top">
        <span className="brand">Front Door</span>
        <span className="brand-for">{buyer ? buyerLabel(buyer) : 'for Valio Aimo'}</span>
        {!needsSetup && (
          <nav aria-label="Main">
            <button type="button" className="link" aria-current={view === 'order' ? 'page' : undefined} onClick={() => setView('order')}>
              Order
            </button>
            <button type="button" className="link" aria-current={view === 'menu' ? 'page' : undefined} onClick={() => setView('menu')}>
              Menu
            </button>
            <button type="button" className="link" aria-current={view === 'rules' ? 'page' : undefined} onClick={() => setView('rules')}>
              Rules
            </button>
            <button type="button" className="link" aria-current={view === 'history' ? 'page' : undefined} onClick={() => setView('history')}>
              History
            </button>
            <button type="button" className="link" onClick={() => keysDialog.current?.showModal()}>
              Keys
            </button>
          </nav>
        )}
      </header>

      <dialog ref={keysDialog} className="sheet" aria-labelledby="keys-dialog-title">
        <KeysForm titleId="keys-dialog-title" title="Keys" onSaved={keysSaved} onCancel={() => keysDialog.current?.close()} />
      </dialog>

      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      <main>
        {MOCK && <p className="mock">Mock mode, no backend. Try “1000 L milk”, “200 L milk drink”, “cream for tomorrow”, “1000 butter, short on stock” or “error”.</p>}
        {offline && (
          <div className="problem banner" role="status">
            <strong>Can’t reach the ordering service.</strong>
            Your request will fail until it’s back. If you run it yourself, start the backend on port 8000.
          </div>
        )}

        {needsSetup ? (
          <KeysForm
            title="Before your first order"
            intro="Two keys connect this screen to Valio. Ask whoever set up your account; you only do this once."
            submitLabel="Save and start"
            onSaved={keysSaved}
          />
        ) : (
          <>
            <section hidden={view !== 'order'} aria-label="Order">
              <form className="ask" onSubmit={submit}>
                <label className="ask-label" htmlFor="text">
                  What do you need?
                </label>
                <textarea
                  id="text"
                  className="ask-field"
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={EXAMPLE}
                  required
                />
                <div className="ask-row">
                  <label className="date-pick">
                    Delivery <strong className="num">{formatDay(date)}</strong>
                    <input
                      type="date"
                      aria-label="Delivery date"
                      value={date}
                      onChange={(e) => e.target.value && setDate(e.target.value)}
                      onClick={(e) => e.currentTarget.showPicker?.()}
                      required
                    />
                  </label>
                  <button type="submit" className="btn" disabled={running || deciding || !text.trim()}>
                    {running ? 'Asking…' : 'Ask the agent'}
                  </button>
                </div>
              </form>

              {running && (
                <div className="working">
                  <p>{RUNNING}</p>
                  <div className="working-bar" aria-hidden="true" />
                </div>
              )}
              {error && (
                <div className="problem" role="alert">
                  <strong>That didn’t go through.</strong>
                  {error}
                </div>
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

            <section hidden={view !== 'menu'} aria-label="Menu">
              <MenuPlanner onAction={refreshAudit} onBusy={setDeciding} onAnnounce={setAnnounce} />
            </section>

            <section hidden={view !== 'rules'} aria-label="Rules">
              <Rules refreshKey={auditKey} onAction={refreshAudit} onAnnounce={setAnnounce} />
            </section>

            <section hidden={view !== 'history'} aria-label="History">
              <AuditLog refreshKey={auditKey} onBuyer={setBuyer} />
            </section>
          </>
        )}
      </main>
    </>
  )
}

function KeysForm({
  title, titleId, intro, submitLabel = 'Save keys', onSaved, onCancel,
}: { title: string; titleId?: string; intro?: string; submitLabel?: string; onSaved: () => void; onCancel?: () => void }) {
  const [keys, setDraft] = useState<ApiKeys>(getKeys)
  function save(e: FormEvent) {
    e.preventDefault()
    setKeys(keys)
    onSaved()
  }
  return (
    <form className="setup" onSubmit={save}>
      <div className="field">
        <h1 className="title" id={titleId}>
          {title}
        </h1>
        {intro && <p className="note">{intro}</p>}
      </div>
      <SecretField
        id="agent-key"
        label="Agent key"
        help="Lets the agent place orders for your kitchen."
        value={keys.agentKey}
        onChange={(v) => setDraft({ ...keys, agentKey: v })}
      />
      <SecretField
        id="approver-key"
        label="Approver key"
        help="Yours alone. It approves orders and shows the history."
        value={keys.approverKey}
        onChange={(v) => setDraft({ ...keys, approverKey: v })}
      />
      <div className="actions">
        <button type="submit" className="btn" disabled={!keys.agentKey.trim() || !keys.approverKey.trim()}>
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="btn plain" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}

function SecretField({ id, label, help, value, onChange }: { id: string; label: string; help: string; value: string; onChange: (v: string) => void }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <p className="field-help" id={`${id}-help`}>
        {help}
      </p>
      <div className="field-row">
        <input
          id={id}
          type={shown ? 'text' : 'password'}
          autoComplete="off"
          spellCheck={false}
          aria-describedby={`${id}-help`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className="btn plain" aria-pressed={shown} aria-controls={id} onClick={() => setShown((s) => !s)}>
          {shown ? 'Hide' : 'Show'}
        </button>
      </div>
    </div>
  )
}

// Only a failure is worth saying; a healthy backend stays silent.
function useBackendDown(): boolean {
  const [down, setDown] = useState(false)
  useEffect(() => {
    let cancelled = false
    getHealth().then(
      () => !cancelled && setDown(false),
      () => !cancelled && setDown(true),
    )
    return () => {
      cancelled = true
    }
  }, [])
  return down
}
