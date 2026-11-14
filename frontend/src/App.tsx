import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { ApiError, askAgentStream, DROPPED, getAdminKey, getHealth, getKeys, setAdminKey, getOrder, MOCK, setKeys, transcribe, VOICE_READY, type ApiKeys } from './api'
import { AuditLog, Recent } from './AuditLog'
import { buyerLabel, errorText, nextMonday } from './format'
import { groupHistory } from './history'
import { COPIES, CopyContext, initialLang, rememberLang, useCopy, type Lang } from './i18n'
import { MenuResult } from './Menu'
import { Rules } from './Rules'
import { RunResult } from './RunResult'
import type { AskResponse, AuditEntry, Reason } from './types'
import { UrgentOptions } from './Urgent'
import { ValioView } from './Valio'
import { languageOf, useReadBack, useVoice, voiceSupported } from './useVoice'
import { usePhaseLine } from './usePhaseLine'
import { MicButton, VoiceStatus } from './Voice'

type View = 'order' | 'rules' | 'history' | 'valio'

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
  const adminDialog = useRef<HTMLDialogElement>(null)
  const [adminKey, setAdminKeyState] = useState(getAdminKey) // Valio staff only: the Valio view appears once it's set
  const field = useRef<HTMLTextAreaElement>(null)
  const [entries, setEntries] = useState<AuditEntry[] | null>(null) // the history the approver key can read
  const [waiting, setWaiting] = useState<number | null>(null) // orders still pending your OK (checked, not guessed)
  const [text, setText] = useState('')
  const [date, setDate] = useState(nextMonday)
  const [dateSet, setDateSet] = useState(false) // the chef picked a date; otherwise the backend reads it from the words
  const [runDate, setRunDate] = useState(date) // the date the shown result was for (follow-up orders reuse it)
  const [result, setResult] = useState<AskResponse | null>(null)
  // A question wins: "How much cream?" and "Order again?" come with the run attached, but only the question is shown.
  const question = result?.question ? result : null
  const run = !question && result?.intent === 'order' && 'lines' in result ? result : null
  const menu = !question && result?.intent === 'menu' && 'lines' in result ? result : null
  const convo = question?.conversation_id ?? null // the question can be answered right here (typed or spoken)
  const convoRef = useRef(convo)
  useEffect(() => {
    convoRef.current = convo
  }, [convo])
  // A menu without a guest count gets a number field; any other question is said plainly, with the box open.
  const asksGuests = question?.intent === 'menu' && question.covers == null && /guest|hengel|vier/i.test(question.question)
  const example = useCyclingExample(text === '', c.EXAMPLES)
  // Voice: the words land in the box (editable), then the request goes as if typed. The answer is read back.
  const [byVoice, setByVoice] = useState(false)
  const readBack = useReadBack()
  const voice = useVoice(transcribe, (words) => {
    readBack.forget()
    setByVoice(true)
    if (convoRef.current) return void ask(words, convoRef.current) // the spoken answer to the agent's question
    setText(words)
    void ask(words)
  })
  const micOn = VOICE_READY && voiceSupported()
  const [editing, setEditing] = useState(false) // phone: the composer is collapsed to a summary row after a result
  const [running, setRunning] = useState(false)
  const [sent, setSent] = useState('') // the words just sent, shown as the chat bubble
  const [error, setError] = useState<string | null>(null)
  const [expired, setExpired] = useState(false) // a follow-up came too late: offer to ask the original again
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  const phaseLine = usePhaseLine(400)
  const refreshAudit = () => setAuditKey((k) => k + 1)
  const offline = useBackendDown()
  const onEntries = useCallback((e: AuditEntry[]) => setEntries(e), [])

  const needsSetup = !MOCK && (!savedKeys.agentKey || !savedKeys.approverKey)
  const groups = useMemo(() => (entries ? groupHistory(entries, c) : []), [entries, c])
  const buyer = entries?.find((e) => e.input)?.input.request.buyer_id ?? null // security events have no request
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

  // The Valio view: a small link asks for the admin key; once it's set, "Valio" sits in the nav.
  function openAdmin() {
    keysDialog.current?.close()
    adminDialog.current?.showModal()
  }
  function adminSaved() {
    setAdminKeyState(getAdminKey())
    adminDialog.current?.close()
    setView('valio')
  }
  function forgetAdmin() {
    setAdminKey('')
    setAdminKeyState('')
    setView('order')
  }

  function keysSaved() {
    setSavedKeys(getKeys())
    keysDialog.current?.close()
    refreshAudit()
  }

  // A new request, or (with `to`) the answer to the question the agent just asked.
  async function ask(words: string, to?: string, when?: string) {
    setSent(words.trim())
    setRunning(true)
    setAnnounce(u.ask.announce)
    setError(null)
    setExpired(false)
    // An answer keeps its question on screen (with "Sending…" and the progress) until the new result replaces it.
    if (!to) setResult(null)
    setEditing(false)
    try {
      phaseLine.reset()
      const input = to ? { text: '', follow_up: { to, answer: words.trim() } } : { text: words.trim(), ...(when ? { requested_date: when } : dateSet ? { requested_date: date } : {}) }
      const res = await askAgentStream(input, (p) =>
        phaseLine.push(c.UI.progress.phases[p.phase] ?? p.text),
      )
      await phaseLine.settle() // let the last step be read before the answer replaces it
      setRunDate(res.requested_date ?? date)
      if (!dateSet && res.requested_date) setDate(res.requested_date) // show the date that was used
      setResult(res)
      if (res.question) {
        setAnnounce(c.question(res.question, res.decision?.reasons[0]))
        setEditing(true) // the answer goes in the box (or the guests field), so keep it open
      }
    } catch (err) {
      const expired = !!to && err instanceof ApiError && err.status === 404
      if (expired) {
        setResult(null) // the question is gone; "Ask again" re-sends the original request
        setExpired(true)
        setEditing(true)
      }
      setError(expired ? u.question.expired : err instanceof Error && err.message === DROPPED ? u.progress.dropped : errorText(err))
      setAnnounce(expired ? u.question.expired : '')
      if (expired && byVoice) readBack.speak(u.question.expired, { lang: languageOf(text) })
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
    if (convo) return void ask(String(n), convo)
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

  // "Order again?": yes resends it as an answer (or, without a conversation, the same words with "again").
  function orderAgain() {
    if (convo) return void ask(u.question.orderAgain, convo)
    const again = `${text.trim()} again`
    setText(again)
    void ask(again)
  }
  function leaveIt() {
    setResult(null)
    setAnnounce(u.question.leftAlone)
  }

  // For a request made by voice, the backend's one-sentence read-back is said aloud in the request's language. When it
  // asked something answerable, the mic then opens by itself for the answer (Cancel stops it; typing works too).
  const { speak } = readBack
  const lang = languageOf(text)
  const voiceRef = useRef(voice)
  useEffect(() => {
    voiceRef.current = voice
  })
  useEffect(() => {
    if (!byVoice || !result) return
    const line = result.speak ?? announce
    if (!line || line.endsWith('…')) return
    const listen = result.question && result.conversation_id && micOn
      ? () => voiceRef.current.state === 'idle' && void voiceRef.current.start(true, true)
      : undefined
    speak(line, { lang, onEnd: listen })
  }, [announce, byVoice, result, speak, lang, micOn])

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
        <span className="brand-for">{view === 'valio' ? 'Valio Aimo' : buyer ? buyerLabel(buyer) : ''}</span>
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
          {adminKey && (
            <button type="button" className="link" aria-current={view === 'valio' ? 'page' : undefined} onClick={() => setView('valio')}>
              {u.valio.nav}
            </button>
          )}
          <button type="button" className="link lang" onClick={onSwitchLang} aria-label={u.lang.label} title={u.lang.switchTo}>
            {u.lang.short}
          </button>
        </nav>
      </header>

      <dialog ref={keysDialog} className="sheet" aria-labelledby="keys-dialog-title">
        <KeysForm titleId="keys-dialog-title" title={u.keys.title} onSaved={keysSaved} onCancel={() => keysDialog.current?.close()} />
        {!adminKey && <ValioLink onOpen={openAdmin} />}
      </dialog>
      <dialog ref={adminDialog} className="sheet" aria-labelledby="admin-dialog-title">
        <AdminKeyForm onSaved={adminSaved} onCancel={() => adminDialog.current?.close()} />
      </dialog>

      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      <main className={view === 'order' && empty ? 'roomy' : undefined}>
        {MOCK && (
          <p className="mock" role="note">
            <strong>{u.mock.title}</strong> {u.mock.body}
          </p>
        )}
        {offline && (
          <div className="problem banner" role="status">
            <strong>{u.offline.title}</strong>
            {u.offline.body}
          </div>
        )}

        {adminKey && (
          <section hidden={view !== 'valio'} aria-label={u.valio.title}>
            {view === 'valio' && <ValioView refreshKey={auditKey} onForget={forgetAdmin} />}
          </section>
        )}
        {needsSetup ? (
          view !== 'valio' && (
            <>
              <KeysForm title={u.keys.firstTitle} intro={u.keys.firstIntro} submitLabel={u.keys.start} onSaved={keysSaved} />
              {!adminKey && <ValioLink onOpen={openAdmin} />}
            </>
          )
        ) : (
          <>
            <section hidden={view !== 'order'} aria-label={u.nav.order} className={empty ? undefined : 'thread'}>
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
                {micOn && !convo && <MicButton voice={voice} disabled={running || deciding} />}
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
                {micOn && !convo && <VoiceStatus voice={voice} />}
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

              {!empty && sent && <p className="bubble mine">{sent}</p>}
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
                  {expired && text.trim() && (
                    <div className="actions">
                      <button type="button" className="btn" onClick={() => void ask(text)} disabled={running}>
                        {u.question.reask}
                      </button>
                    </div>
                  )}
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
                <Question
                  key={question.conversation_id ?? question.question}
                  question={question.question}
                  more={question.intent === 'unclear'}
                  reason={question.decision?.reasons[0] ?? null}
                  answerable={!!convo}
                  byVoice={byVoice}
                  busy={running}
                  onAnswer={(words) => convo && void ask(words, convo)}
                  onAgain={orderAgain}
                  onLeave={leaveIt}
                  onEdit={retry}
                  mic={micOn && convo ? <MicButton voice={voice} disabled={running} /> : null}
                  status={micOn && convo ? <VoiceStatus voice={voice} /> : null}
                />
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
                  onHistory={() => setView('history')}
                  onPlain={(need) => {
                    const next = `${text.trim()} (regular, not ${need})` // the backend reads "regular" / "not gluten…" as the buyer's own words
                    setText(next)
                    void ask(next, undefined, runDate)
                  }}
                  onAskFor={(next) => {
                    setText(next)
                    void ask(next, undefined, runDate) // same delivery day as the result it came from
                  }}
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

// The next n delivery days from tomorrow (Helsinki), as YYYY-MM-DD.
function nextDays(n: number): string[] {
  const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date())
  const base = Date.parse(`${ymd}T12:00:00Z`)
  return Array.from({ length: n }, (_, i) => new Date(base + (i + 1) * 86_400_000).toISOString().slice(0, 10))
}

// A small way in for Valio's staff; the chef's nav never shows it unless an admin key is set.
function ValioLink({ onOpen }: { onOpen: () => void }) {
  const u = useCopy().UI
  return (
    <p className="note valio-link">
      <button type="button" className="link accent flush-link" onClick={onOpen}>
        {u.valio.open}
      </button>
    </p>
  )
}

function AdminKeyForm({ onSaved, onCancel }: { onSaved: () => void; onCancel: () => void }) {
  const u = useCopy().UI
  const [key, setKey] = useState('')
  return (
    <form
      className="setup"
      onSubmit={(e) => {
        e.preventDefault()
        setAdminKey(key)
        setKey('')
        onSaved()
      }}
    >
      <div className="field">
        <h1 className="title" id="admin-dialog-title">
          {u.valio.keyTitle}
        </h1>
        <p className="note">{u.valio.keyIntro}</p>
      </div>
      <SecretField id="admin-key" label={u.valio.key} help={u.valio.keyHelp} value={key} onChange={setKey} />
      <div className="actions">
        <button type="submit" className="btn" disabled={!key.trim()}>
          {u.valio.open2}
        </button>
        <button type="button" className="btn plain" onClick={onCancel}>
          {u.keys.cancel}
        </button>
      </div>
    </form>
  )
}

// The agent's question, with the answer right there: typed in the field, or spoken (the mic opens by itself after a
// spoken question). "Order again?" is two buttons instead. Questions that can't be answered here (off-topic, a date
// in the past) leave the box open above.
function Question(p: {
  question: string; more: boolean; reason: Reason | null; answerable: boolean; byVoice: boolean; busy: boolean
  onAnswer: (words: string) => void; onAgain: () => void; onLeave: () => void; onEdit: () => void; mic: ReactNode; status: ReactNode
}) {
  const c = useCopy()
  const u = c.UI
  const [words, setWords] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  const field = useRef<HTMLInputElement>(null)
  const again = p.reason?.facts.minutes_ago != null
  // "For which delivery day?": the next days as one-tap answers (sent as "20.11.", which the backend reads exactly).
  const askingDay = p.answerable && /which delivery day/i.test(p.question)
  const days = askingDay ? nextDays(6) : []
  // "Which one did you mean: 1) A; 2) B; 3) C? Or say it more precisely.": the options as one-tap answers ("2").
  const options = p.answerable ? (/^Which one did you mean: (.+)\? Or say it more precisely\.?$/.exec(p.question)?.[1].split('; ').map((o) => o.replace(/^\d\)\s*/, '')) ?? []) : []
  useEffect(() => {
    // typing: straight into the answer field; by voice the mic is listening, so focus just brings the question into view
    if (p.answerable && !again && !p.byVoice) field.current?.focus()
    else heading.current?.focus()
  }, [p.answerable, again, p.byVoice])
  return (
    <section className="answer" aria-label={u.question.status}>
      <p className="status neutral">{p.more ? u.question.more : u.question.status}</p>
      <h2 ref={heading} tabIndex={-1} className="answer-text">
        {c.question(p.question, p.reason)}
      </h2>
      {!again && p.reason?.suggested_fix && !p.answerable && <p className="answer-sub">{p.reason.suggested_fix}</p>}
      {!again && !p.answerable && (
        <div className="actions">
          <button type="button" className="btn plain accent-text" onClick={p.onEdit}>
            {u.question.edit}
          </button>
        </div>
      )}
      {options.length > 0 && (
        <div className="chips" role="group" aria-label={u.question.options}>
          {options.map((o, n) => (
            <button key={o} type="button" className="chip" onClick={() => p.onAnswer(String(n + 1))} disabled={p.busy}>
              {c.tidyName(o)}
            </button>
          ))}
        </div>
      )}
      {days.length > 0 && (
        <div className="chips" role="group" aria-label={u.question.days}>
          {days.map((d) => (
            <button key={d} type="button" className="chip" onClick={() => p.onAnswer(`${Number(d.slice(8))}.${Number(d.slice(5, 7))}.`)} disabled={p.busy}>
              {c.day(d)}
            </button>
          ))}
        </div>
      )}
      {again ? (
        <div className="actions">
          <button type="button" className="btn" onClick={p.onAgain} disabled={p.busy}>
            {p.busy ? u.question.sending : u.question.orderAgain}
          </button>
          <button type="button" className="btn plain" onClick={p.onLeave} disabled={p.busy}>
            {u.question.leave}
          </button>
        </div>
      ) : (
        p.answerable && (
          <form
            className="guests"
            onSubmit={(e) => {
              e.preventDefault()
              if (words.trim()) p.onAnswer(words)
            }}
          >
            <div className="ask-inputs">
              <div className="ask-box answer-box">
                <input
                  ref={field}
                  className={`answer-input${p.mic ? ' with-mic' : ''}`}
                  aria-label={u.question.answer}
                  placeholder={u.question.answer}
                  value={words}
                  onChange={(e) => setWords(e.target.value)}
                  disabled={p.busy}
                  enterKeyHint="send"
                />
                {p.mic}
              </div>
              <button type="submit" className="btn" disabled={p.busy || !words.trim()}>
                {p.busy ? u.question.sending : u.question.send}
              </button>
            </div>
            {p.status}
          </form>
        )
      )}
    </section>
  )
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
