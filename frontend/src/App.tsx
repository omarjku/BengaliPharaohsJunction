import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { askAgentStream, DROPPED, getHealth, getKeys, getOrder, MOCK, setKeys, transcribe, VOICE_READY, type ApiKeys } from './api'
import { AuditLog, Recent } from './AuditLog'
import { errorText, nextMonday } from './format'
import { groupHistory } from './history'
import { COPIES, CopyContext, initialLang, rememberLang, useCopy, type Lang } from './i18n'
import { MenuResult } from './Menu'
import { Rules } from './Rules'
import { RunResult } from './RunResult'
import type { AskResponse, AuditEntry } from './types'
import { UrgentOptions } from './Urgent'
import { useReadBack, useVoice, voiceSupported } from './useVoice'
import { usePhaseLine } from './usePhaseLine'
import { MicButton, VoiceStatus } from './Voice'

type View = 'order' | 'rules' | 'history'

// "lapland-kitchen" -> "Lapland kitchen": the buyer id is all the API tells us about the buyer.
const buyerLabel = (id: string) => id.replace(/[-_.]+/g, ' ').replace(/^./, (c) => c.toUpperCase())
const partOfDay = () => {
  const h = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Europe/Helsinki' }).format(new Date()))
  return h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening'
}
// Cmd/Ctrl+Enter sends the form from a textarea.
const submitOnCmdEnter = (e: KeyboardEvent<HTMLTextAreaElement>) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    e.currentTarget.form?.requestSubmit()
  }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(initialLang)
  const c = COPIES[lang]
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  function switchLang() {
    const next = lang === 'fi' ? 'en' : 'fi'
    setLang(next)
    rememberLang(next)
  }
  return (
    <CopyContext.Provider value={c}>
      <Screen onSwitchLang={switchLang} />
    </CopyContext.Provider>
  )
}

function Screen({ onSwitchLang }: { onSwitchLang: () => void }) {
  const c = useCopy()
  const u = c.UI
  const [view, setView] = useState<View>('order')
  const [savedKeys, setSavedKeys] = useState(getKeys)
  const keysDialog = useRef<HTMLDialogElement>(null)
  const field = useRef<HTMLTextAreaElement>(null)
  const [entries, setEntries] = useState<AuditEntry[] | null>(null) // the history the approver key can read
  const [waiting, setWaiting] = useState<number | null>(null) // orders still pending your OK (checked, not guessed)
  const [text, setText] = useState('')
  const [date, setDate] = useState(nextMonday)
  const [dateSet, setDateSet] = useState(false) // the chef picked a date; otherwise the backend reads it from the words
  const [runDate, setRunDate] = useState(date) // the date the shown result was for (follow-up orders reuse it)
  const [result, setResult] = useState<AskResponse | null>(null)
  const run = result?.intent === 'order' && 'lines' in result ? result : null
  const menu = result?.intent === 'menu' && 'lines' in result ? result : null
  const question = result?.question ? result : null
  // A menu without a guest count gets a number field; any other question is said plainly, with the box open.
  const asksGuests = question?.intent === 'menu' && question.covers == null && /guest|hengel|vier/i.test(question.question)
  const example = useCyclingExample(text === '', c.EXAMPLES)
  // Voice: the words land in the box (editable), then the request goes as if typed. The answer is read back.
  const [byVoice, setByVoice] = useState(false)
  const readBack = useReadBack()
  const voice = useVoice(transcribe, (words) => {
    readBack.forget()
    setText(words)
    setByVoice(true)
    void ask(words)
  })
  const micOn = VOICE_READY && voiceSupported()
  const [editing, setEditing] = useState(false) // phone: the composer is collapsed to a summary row after a result
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  const phaseLine = usePhaseLine(400)
  const refreshAudit = () => setAuditKey((k) => k + 1)
  const offline = useBackendDown()
  const onEntries = useCallback((e: AuditEntry[]) => setEntries(e), [])

  const needsSetup = !MOCK && (!savedKeys.agentKey || !savedKeys.approverKey)
  const groups = useMemo(() => (entries ? groupHistory(entries, c) : []), [entries, c])
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
    const held = groups.filter((g) => g.outcomeKey === 'held' && g.orderId).slice(0, 5)
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

  async function ask(words: string) {
    setRunning(true)
    setAnnounce(u.ask.announce)
    setError(null)
    setResult(null)
    setEditing(false)
    try {
      phaseLine.reset()
      const res = await askAgentStream({ text: words.trim(), ...(dateSet ? { requested_date: date } : {}) }, (p) =>
        phaseLine.push(c.UI.progress.phases[p.phase] ?? p.text),
      )
      await phaseLine.settle() // let the last step be read before the answer replaces it
      setRunDate(res.requested_date ?? date)
      if (!dateSet && res.requested_date) setDate(res.requested_date) // show the date that was used
      setResult(res)
      if (res.question) {
        setAnnounce(res.question)
        setEditing(true) // the answer goes in the box (or the guests field), so keep it open
      }
    } catch (err) {
      setError(err instanceof Error && err.message === DROPPED ? u.progress.dropped : errorText(err))
      setAnnounce('')
    } finally {
      setRunning(false)
      refreshAudit()
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    setByVoice(false)
    void ask(text)
  }

  // "For how many guests?" answered inline: the words go into the box and the agent reads it again.
  function answerGuests(n: number) {
    const next = `${text.trim().replace(/[.\s]*$/, '')}. ${u.question.guests(n)}`
    setText(next)
    void ask(next)
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

  // Read the answer's first sentence aloud for a request made by voice (status + headline, as announced).
  const { speak } = readBack
  useEffect(() => {
    if (byVoice && result && announce && !announce.endsWith('…')) speak(announce)
  }, [announce, byVoice, result, speak])

  const empty = !result && !running && !error
  const collapsed = !!(run || menu) && !editing
  const urgent = (run || menu)?.urgent_options
  const urgentBlock = urgent && urgent.length > 0 ? <UrgentOptions options={urgent} /> : null

  return (
    <>
      <header className="top">
        <span className="brand">
          <DoorGlyph /> Front Door
        </span>
        <span className="brand-for">{buyer ? buyerLabel(buyer) : ''}</span>
        <nav aria-label={u.nav.main}>
          {!needsSetup &&
            (['order', 'history', 'rules'] as const).map((v) => (
              <button key={v} type="button" className="link" aria-current={view === v ? 'page' : undefined} onClick={() => setView(v)}>
                {u.nav[v]}
              </button>
            ))}
          {!needsSetup && (
            <button type="button" className="link" onClick={() => keysDialog.current?.showModal()}>
              {u.nav.keys}
            </button>
          )}
          <button type="button" className="link lang" onClick={onSwitchLang} aria-label={u.lang.label} title={u.lang.switchTo}>
            {u.lang.short}
          </button>
        </nav>
      </header>

      <dialog ref={keysDialog} className="sheet" aria-labelledby="keys-dialog-title">
        <KeysForm titleId="keys-dialog-title" title={u.keys.title} onSaved={keysSaved} onCancel={() => keysDialog.current?.close()} />
      </dialog>

      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      <main className={view === 'order' && empty ? 'roomy' : undefined}>
        {offline && (
          <div className="problem banner" role="status">
            <strong>{u.offline.title}</strong>
            {u.offline.body}
          </div>
        )}

        {needsSetup ? (
          <KeysForm title={u.keys.firstTitle} intro={u.keys.firstIntro} submitLabel={u.keys.start} onSaved={keysSaved} />
        ) : (
          <>
            <section hidden={view !== 'order'} aria-label={u.nav.order}>
              <h1 className="sr-only">{u.nav.order}</h1>
              {empty && waiting !== null && <p className="greeting">{u.greeting(partOfDay(), approver, waiting)}</p>}
              {collapsed && (
                <button type="button" className="composer-summary" onClick={retry}>
                  <span className="composer-text">{text.trim()}</span>
                  <span className="quiet num">{c.day(runDate)}</span>
                  <span className="accent-text">{u.ask.edit}</span>
                </button>
              )}
              <form className={`ask${empty ? ' first' : ''}${collapsed ? ' collapsible' : ''}`} onSubmit={submit}>
                <label className="ask-label" htmlFor="text">
                  {u.ask.label}
                </label>
                <div className="ask-box">
                <textarea
                  id="text"
                  ref={field}
                  className={`ask-field${micOn ? ' with-mic' : ''}`}
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={submitOnCmdEnter}
                  placeholder={example}
                  aria-describedby="text-help"
                  required
                />
                {micOn && <MicButton voice={voice} disabled={running || deciding} />}
                </div>
                <p className="sr-only" id="text-help">
                  {u.ask.help(c.EXAMPLES)}
                </p>
                <div className="ask-row">
                  <label className="date-pick">
                    {u.ask.delivery} <strong className="num">{c.day(date)}</strong>
                    {!dateSet && <span className="faint small">{u.ask.orDay}</span>}
                    <input
                      type="date"
                      aria-label={u.ask.dateAria}
                      value={date}
                      onChange={(e) => {
                        if (!e.target.value) return
                        setDate(e.target.value)
                        setDateSet(true)
                      }}
                      onClick={(e) => e.currentTarget.showPicker?.()}
                      required
                    />
                  </label>
                  {/* One primary per screen: once there's an answer, asking again is the quiet option. */}
                  <button type="submit" className={`btn${result ? ' plain accent-text' : ''}`} disabled={running || deciding || !text.trim()}>
                    {running ? u.ask.asking : result ? u.ask.again : u.ask.ask}
                  </button>
                </div>
                {micOn && <VoiceStatus voice={voice} />}
                {empty && (
                  <p className="try">
                    {MOCK ? u.ask.tryDemo : u.ask.try}
                    {c.TRY.map((t, i) => (
                      <span key={t}>
                        {i > 0 && <span className="sep"> · </span>}
                        <button type="button" className="link accent inline" onClick={() => setText(t)}>
                          {t}
                        </button>
                      </span>
                    ))}
                  </p>
                )}
              </form>

              {running && (
                <div className="working" role="status" aria-label={u.progress.aria}>
                  {/* Re-keyed per phase, so each step fades in; the status region reads each step out politely. */}
                  <p key={phaseLine.phase ?? 'start'} className="phase">
                    {phaseLine.phase ?? u.progress.phases.understanding}
                  </p>
                  <div className="working-bar" aria-hidden="true" />
                </div>
              )}
              {error && (
                <div className="problem" role="alert">
                  <strong>{u.failed}</strong>
                  {error}
                </div>
              )}
              {byVoice && result && readBack.canSpeak && (
                <p className="voice-status readback">
                  {readBack.muted ? u.voice.readOff : u.voice.readOn}{' '}
                  <button type="button" className="link accent inline" aria-pressed={readBack.muted} onClick={readBack.toggle}>
                    {readBack.muted ? u.voice.turnOn : u.voice.mute}
                  </button>
                </p>
              )}
              {question && asksGuests && (
                <GuestsQuestion key={question.audit_id ?? question.question} question={question.question} onAnswer={answerGuests} busy={running} />
              )}
              {question && !asksGuests && (
                <section className="answer" aria-label={u.question.status}>
                  <p className="status neutral">{question.intent === 'unclear' ? u.question.more : u.question.status}</p>
                  <h2 className="answer-text">{question.question}</h2>
                  {question.decision?.reasons[0]?.suggested_fix && <p className="answer-sub">{question.decision.reasons[0].suggested_fix}</p>}
                </section>
              )}
              {menu && (
                <MenuResult
                  key={menu.audit_id}
                  plan={menu}
                  covers={menu.covers ?? null}
                  requestedDate={runDate}
                  onAction={refreshAudit}
                  onBusy={setDeciding}
                  onAnnounce={setAnnounce}
                  after={urgentBlock}
                />
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
                  after={urgentBlock}
                />
              )}
              {empty && <Recent groups={groups.slice(0, 3)} onOpen={() => setView('history')} />}
            </section>

            <section hidden={view !== 'rules'} aria-label={u.nav.rules}>
              <Rules refreshKey={auditKey} onAction={refreshAudit} onAnnounce={setAnnounce} />
            </section>

            <section hidden={view !== 'history'} aria-label={u.nav.history}>
              <AuditLog refreshKey={auditKey} onEntries={onEntries} />
            </section>
          </>
        )}
      </main>
    </>
  )
}

// The box's grey example cycles slowly while it's empty, so a milk order, a kebab shop and a menu all see themselves.
// It's only a placeholder: it disappears as soon as anyone types, and it stays still under reduced motion.
function useCyclingExample(active: boolean, examples: string[]): string {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (!active || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const t = setInterval(() => setI((n) => (n + 1) % examples.length), 3500)
    return () => clearInterval(t)
  }, [active, examples.length])
  return examples[i % examples.length]
}

// "For how many guests?" with the answer right there.
function GuestsQuestion({ question, onAnswer, busy }: { question: string; onAnswer: (n: number) => void; busy: boolean }) {
  const u = useCopy().UI
  const [guests, setGuests] = useState('')
  const n = Number(guests)
  const ok = Number.isInteger(n) && n >= 1 && n <= 2000
  const field = useRef<HTMLInputElement>(null)
  useEffect(() => field.current?.focus(), [])
  return (
    <section className="answer" aria-label={u.question.status}>
      <p className="status neutral">{u.question.status}</p>
      <form
        className="guests"
        onSubmit={(e) => {
          e.preventDefault()
          if (ok) onAnswer(n)
        }}
      >
        <label className="answer-text" htmlFor="guests">
          {question}
        </label>
        <div className="ask-inputs">
          <input ref={field} id="guests" className="guests-input num" type="number" inputMode="numeric" min={1} max={2000} value={guests} onChange={(e) => setGuests(e.target.value)} />
          <button type="submit" className="btn" disabled={!ok || busy}>
            {busy ? u.question.planning : u.question.plan}
          </button>
        </div>
      </form>
    </section>
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
  title, titleId, intro, submitLabel, onSaved, onCancel,
}: { title: string; titleId?: string; intro?: string; submitLabel?: string; onSaved: () => void; onCancel?: () => void }) {
  const k = useCopy().UI.keys
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
      <SecretField id="agent-key" label={k.agent} help={k.agentHelp} value={keys.agentKey} onChange={(v) => setDraft({ ...keys, agentKey: v })} />
      <SecretField id="approver-key" label={k.approver} help={k.approverHelp} value={keys.approverKey} onChange={(v) => setDraft({ ...keys, approverKey: v })} />
      <div className="actions">
        <button type="submit" className="btn" disabled={!keys.agentKey.trim() || !keys.approverKey.trim()}>
          {submitLabel ?? k.save}
        </button>
        {onCancel && (
          <button type="button" className="btn plain" onClick={onCancel}>
            {k.cancel}
          </button>
        )}
      </div>
    </form>
  )
}

function SecretField({ id, label, help, value, onChange }: { id: string; label: string; help: string; value: string; onChange: (v: string) => void }) {
  const k = useCopy().UI.keys
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
          {shown ? k.hide : k.show}
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
