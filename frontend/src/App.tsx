import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { getHealth, getKeys, getOrder, MOCK, runAgent, setKeys, type ApiKeys } from './api'
import { AuditLog, Recent } from './AuditLog'
import { EXAMPLE, RUNNING, TRY } from './copy'
import { errorText, formatDay, nextMonday } from './format'
import { groupHistory } from './history'
import { MenuPlanner } from './Menu'
import { Rules } from './Rules'
import { RunResult } from './RunResult'
import type { AgentRun, AuditEntry } from './types'

type View = 'order' | 'menu' | 'rules' | 'history'

// "lapland-kitchen" -> "Lapland kitchen": the buyer id is all the API tells us about the buyer.
const buyerLabel = (id: string) => id.replace(/[-_.]+/g, ' ').replace(/^./, (c) => c.toUpperCase())
const greeting = () => {
  const h = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Europe/Helsinki' }).format(new Date()))
  return h < 12 ? 'Morning' : h < 18 ? 'Afternoon' : 'Evening'
}
// Cmd/Ctrl+Enter sends the form from a textarea.
const submitOnCmdEnter = (e: KeyboardEvent<HTMLTextAreaElement>) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    e.currentTarget.form?.requestSubmit()
  }
}

export default function App() {
  const [view, setView] = useState<View>('order')
  const [savedKeys, setSavedKeys] = useState(getKeys)
  const keysDialog = useRef<HTMLDialogElement>(null)
  const field = useRef<HTMLTextAreaElement>(null)
  const [entries, setEntries] = useState<AuditEntry[] | null>(null) // the history the approver key can read
  const [waiting, setWaiting] = useState<number | null>(null) // orders still pending your OK (checked, not guessed)
  const [text, setText] = useState('')
  const [date, setDate] = useState(nextMonday)
  const [runDate, setRunDate] = useState(date) // the date the shown run was for (follow-up orders reuse it)
  const [run, setRun] = useState<AgentRun | null>(null)
  const [editing, setEditing] = useState(false) // phone: the composer is collapsed to a summary row after a result
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  const refreshAudit = () => setAuditKey((k) => k + 1)
  const offline = useBackendDown()
  const onEntries = useCallback((e: AuditEntry[]) => setEntries(e), [])

  const needsSetup = !MOCK && (!savedKeys.agentKey || !savedKeys.approverKey)
  const groups = useMemo(() => (entries ? groupHistory(entries) : []), [entries])
  const buyer = entries?.[0]?.input.request.buyer_id ?? null
  const approver = useMemo(() => {
    for (const e of [...(entries ?? [])].reverse()) {
      const m = /^human:(.+?):(approve|reject|mandate)$/.exec(e.actor)
      if (m) return m[1]
    }
    return null
  }, [entries])

  // "Do I need to do anything?" Only orders the front door still lists as pending count.
  useEffect(() => {
    const held = groups.filter((g) => g.outcome === 'Held for your OK' && g.orderId).slice(0, 5)
    if (!held.length) {
      setWaiting(entries ? 0 : null)
      return
    }
    let cancelled = false
    Promise.all(held.map((g) => getOrder(g.orderId!).then((o) => o.status === 'pending_approval', () => false))).then(
      (r) => !cancelled && setWaiting(r.filter(Boolean).length),
    )
    return () => {
      cancelled = true
    }
  }, [groups, entries])

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
    setEditing(false)
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

  // "Not this one": back to the request, cursor at the end, ready for more detail.
  function retry() {
    setEditing(true)
    setView('order')
    requestAnimationFrame(() => {
      const f = field.current
      if (!f) return
      f.focus()
      f.setSelectionRange(f.value.length, f.value.length)
    })
  }

  const empty = !run && !running && !error
  const collapsed = !!run && !editing

  return (
    <>
      <header className="top">
        <span className="brand">
          <DoorGlyph /> Front Door
        </span>
        <span className="brand-for">{buyer ? buyerLabel(buyer) : ''}</span>
        {!needsSetup && (
          <nav aria-label="Main">
            {(['order', 'menu', 'rules', 'history'] as const).map((v) => (
              <button key={v} type="button" className="link" aria-current={view === v ? 'page' : undefined} onClick={() => setView(v)}>
                {{ order: 'Order', menu: 'Menu', rules: 'Rules', history: 'History' }[v]}
              </button>
            ))}
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

      <main className={view === 'order' && empty ? 'roomy' : undefined}>
        {offline && (
          <div className="problem banner" role="status">
            <strong>Can’t reach the ordering service.</strong>
            Your request will fail until it’s back. If you run it yourself, start the backend on port 8000.
          </div>
        )}

        {needsSetup ? (
          <KeysForm
            title="Before your first order"
            intro="Paste the two keys from your Valio Aimo account. You only do this once."
            submitLabel="Save and start"
            onSaved={keysSaved}
          />
        ) : (
          <>
            <section hidden={view !== 'order'} aria-label="Order">
              {empty && waiting !== null && (
                <p className="greeting">
                  {greeting()}
                  {approver ? `, ${approver}` : ''}.{' '}
                  {waiting === 0 ? 'Nothing waiting for you.' : `${waiting} order${waiting === 1 ? ' is' : 's are'} waiting for your OK in History.`}
                </p>
              )}
              {collapsed && (
                <button type="button" className="composer-summary" onClick={retry}>
                  <span className="composer-text">{text.trim()}</span>
                  <span className="quiet num">{formatDay(runDate)}</span>
                  <span className="accent-text">Edit</span>
                </button>
              )}
              <form className={`ask${empty ? ' first' : ''}${collapsed ? ' collapsible' : ''}`} onSubmit={submit}>
                <label className="ask-label" htmlFor="text">
                  What do you need?
                </label>
                <textarea
                  id="text"
                  ref={field}
                  className="ask-field"
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={submitOnCmdEnter}
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
                  {/* One primary per screen: once there's an answer, asking again is the quiet option. */}
                  <button type="submit" className={`btn${run ? ' plain accent-text' : ''}`} disabled={running || deciding || !text.trim()}>
                    {running ? 'Asking…' : run ? 'Ask again' : 'Ask the agent'}
                  </button>
                </div>
                {empty && (
                  <p className="try">
                    {MOCK ? 'Demo data. Try: ' : 'Try: '}
                    {TRY.map((t, i) => (
                      <span key={t}>
                        {i > 0 && ' · '}
                        <button type="button" className="link accent inline" onClick={() => setText(t)}>
                          {t}
                        </button>
                      </span>
                    ))}
                  </p>
                )}
              </form>

              {running && (
                <div className="working" role="status">
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
                  onRetry={retry}
                />
              )}
              {empty && <Recent groups={groups.slice(0, 3)} onOpen={() => setView('history')} />}
            </section>

            <section hidden={view !== 'menu'} aria-label="Menu">
              <MenuPlanner onAction={refreshAudit} onBusy={setDeciding} onAnnounce={setAnnounce} />
            </section>

            <section hidden={view !== 'rules'} aria-label="Rules">
              <Rules refreshKey={auditKey} onAction={refreshAudit} onAnnounce={setAnnounce} />
            </section>

            <section hidden={view !== 'history'} aria-label="History">
              <AuditLog refreshKey={auditKey} onEntries={onEntries} />
            </section>
          </>
        )}
      </main>
    </>
  )
}

// A door, drawn in two strokes: the product's name, not decoration.
function DoorGlyph() {
  return (
    <svg className="door" viewBox="0 0 16 20" width="14" height="18" aria-hidden="true">
      <path d="M2 19V2.5A1.5 1.5 0 0 1 3.5 1h9A1.5 1.5 0 0 1 14 2.5V19M1 19h14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="11" cy="10.5" r="1" fill="currentColor" />
    </svg>
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
      <div className="secret">
        <input
          id={id}
          type={shown ? 'text' : 'password'}
          autoComplete="off"
          spellCheck={false}
          aria-describedby={`${id}-help`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className="secret-toggle" aria-pressed={shown} aria-controls={id} onClick={() => setShown((s) => !s)}>
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
