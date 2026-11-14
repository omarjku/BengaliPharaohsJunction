import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { ApiError, askAgentStream, createSandbox, DROPPED, getAdminKey, getHealth, getKeys, getSandboxSession, KEYS_FROM_LINK, applyLinkKeys, checkLinkKeys, isTryEntry, MOCK, sandboxSessionLive, setAdminKey, setKeys, setSandboxSession, getOrder, transcribe, VOICE_READY, type ApiKeys } from './api'
import { AuditLog, Recent } from './AuditLog'
import { buyerLabel, errorText, nextMonday } from './format'
import { groupHistory } from './history'
import { COPIES, CopyContext, initialLang, rememberLang, useCopy, type Lang } from './i18n'
import { MenuResult } from './Menu'
import { Rules } from './Rules'
import { RunResult } from './RunResult'
import type { AskResponse, AuditEntry, MenuRun, Reason } from './types'
import { UrgentOptions } from './Urgent'
import { ValioView } from './Valio'
import { useVoice, voiceSupported } from './useVoice'
import { usePhaseLine } from './usePhaseLine'
import { DictationMic, MicButton, VoiceStatus } from './Voice'
import { HeaderMenu } from './HeaderMenu'
import './Keys.css'
import { PhotoButton } from './PhotoButton'
import { Composer } from './Composer'
import { Onboarding } from './Onboarding'
import { useOnboarded } from './onboardingApi'
import { Kitchen } from './Kitchen'
import { KitchenChip } from './KitchenChip'
import { onboardingSkippedFor, skipOnboardingFor, useKitchen } from './useKitchen'
import { Conversation, type VoiceLayout } from './Conversation'
import { Calendar } from './Calendar'
import { Orb } from './Orb'
import { useLive } from './useLive'
import { useLiveWarm } from './liveWarm'
import { useTalk, useTalkPhotoAvailable } from './useTalk'

type View = 'order' | 'kitchen' | 'rules' | 'history' | 'valio'
// The conversation thread: the chef's messages, the agent's lines (partial while voice is still forming them), the
// responses (decision cards and questions) and errors (with "Ask again" when a question expired).
type Item =
  | { id: number; kind: 'user' | 'agent'; text: string; partial?: boolean }
  | { id: number; kind: 'res'; res: AskResponse; date: string; asked?: string; have?: string[] } // asked: the request it answers
  | { id: number; kind: 'error'; text: string; reask: string | null }
type NewItem = Item extends infer I ? (I extends Item ? Omit<I, 'id'> : never) : never

const partOfDay = () => {
  const h = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Europe/Helsinki' }).format(new Date()))
  return h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening'
}

function clearTryEntry() {
  const path = window.location.pathname === '/try' ? '/' : window.location.pathname
  window.history.replaceState(null, '', path + window.location.search)
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
  const [sandboxState, setSandboxState] = useState<'idle' | 'setting-up' | 'error'>(() => (isTryEntry() ? 'setting-up' : 'idle'))
  const [sandboxError, setSandboxError] = useState<string | null>(null)
  const sandboxBusy = useRef(false)
  const keysDialog = useRef<HTMLDialogElement>(null)
  const adminDialog = useRef<HTMLDialogElement>(null)
  const [adminKey, setAdminKeyState] = useState(getAdminKey) // Valio staff only: the Valio view appears once it's set
  const field = useRef<HTMLTextAreaElement>(null)
  const [entries, setEntries] = useState<AuditEntry[] | null>(null) // the history the approver key can read
  const [waiting, setWaiting] = useState<number | null>(null) // orders still pending your OK (checked, not guessed)
  const [text, setText] = useState('')
  const [date, setDate] = useState(nextMonday)
  const [result, setResult] = useState<AskResponse | null>(null)
  // A question wins: "How much cream?" and "Order again?" come with the run attached, but only the question is shown.
  const question = result?.question ? result : null
  const convo = question?.conversation_id ?? null // the question can be answered right here (typed or spoken)
  const convoRef = useRef(convo)
  useEffect(() => {
    convoRef.current = convo
  }, [convo])
  // ONE thread for text and voice: the chef's messages, the agent's lines, the decision cards, errors.
  const [thread, setThread] = useState<Item[]>([])
  const nextId = useRef(0)
  const push = useCallback((it: NewItem) => setThread((t) => [...t, { ...it, id: ++nextId.current } as Item]), [])
  const pantry = useRef<string[]>([]) // what the kitchen has for this order only (a pantry photo); sent with the next requests
  const lastRequest = useRef('') // the chef's last request (not an answer): for "Not this one", re-asks, overrides
  // New words in the thread come into view (a new card scrolls itself: RunResult/MenuResult focus their headline).
  useEffect(() => {
    const last = thread[thread.length - 1]
    if (last && last.kind !== 'res') window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })
  }, [thread])
  // Dictation: the spoken words land in the field, to edit and send (the voice conversation is Talk, below).
  const voice = useVoice(transcribe, (words) => setText((t) => (t.trim() ? `${t.trim()} ${words}` : words)))
  const micOn = VOICE_READY && voiceSupported()
  const [running, setRunning] = useState(false)
  const [auditKey, setAuditKey] = useState(0)
  const [deciding, setDeciding] = useState(false) // approve/reject in flight
  const [announce, setAnnounce] = useState('')
  // Opened from a setup link (api.ts read and removed it): say quietly that the keys were saved, or, when other keys
  // were already saved here, ask before replacing them.
  // The notice stays until dismissed, so keys that changed are always noticed.
  const [fromLink, setFromLink] = useState<typeof KEYS_FROM_LINK | 'invalid'>(KEYS_FROM_LINK)
  const [linkKitchen, setLinkKitchen] = useState<string | null | undefined>(undefined) // undefined: still checking
  useEffect(() => {
    if (KEYS_FROM_LINK !== 'confirm') return
    let cancelled = false
    void checkLinkKeys().then(({ valid, kitchen }) => {
      if (cancelled) return
      if (valid) return setLinkKitchen(kitchen)
      applyLinkKeys(false) // a bad key never replaces a working one
      setFromLink('invalid')
    })
    return () => {
      cancelled = true
    }
  }, [])
  function answerLink(replace: boolean) {
    applyLinkKeys(replace)
    setFromLink(replace ? 'saved' : null)
    if (replace) keysSaved()
  }
  const phaseLine = usePhaseLine(400)
  const refreshAudit = useCallback(() => setAuditKey((k) => k + 1), [])
  const offline = useBackendDown()
  // Voice (Talk): the voice button starts it inside the tap; its words and results go into the same thread. Dictation
  // and Talk never hold the mic at once: starting Talk cancels dictation, and the mic button is gone while Talk is on.
  // First run: Room 2's onboarding (Onboarding.tsx) asks about the kitchen once keys are set; skippable (remembered on
  // this device), and reachable later from the memory panel ("Update my kitchen").
  // Skipped / done is remembered per KITCHEN (the key's buyer id), not per device: another kitchen on the same phone
  // (a setup link) still gets asked. Until the kitchen is known it isn't opened (no flicker).
  const kitchen = useKitchen(savedKeys.agentKey)
  const onboarding = useOnboarded()
  const refreshOnboarding = onboarding.refresh
  const [, bumpSkip] = useState(0)
  const onboardingSkipped = kitchen ? onboardingSkippedFor(kitchen) : true
  const onboardingOpen = onboarding.onboarded === false && !onboardingSkipped // first run only; later it lives on the Kitchen tab
  const startSandbox = useCallback(async (fromTry: boolean, fresh = false) => {
    if (sandboxBusy.current) return
    sandboxBusy.current = true
    setSandboxState('setting-up')
    setSandboxError(null)
    try {
      const existing = getSandboxSession()
      const session = !fresh && existing && sandboxSessionLive(existing) ? existing : await createSandbox()
      setSandboxSession(session)
      if (fromTry) clearTryEntry()
      setSavedKeys(getKeys())
      refreshOnboarding()
      refreshAudit()
      setView('order')
      setSandboxState('idle')
    } catch (error) {
      const message = error instanceof ApiError && error.status === 404
        ? u.sandbox.off
        : error instanceof ApiError && error.status === 429
          ? u.sandbox.rateLimited
          : errorText(error)
      setSandboxError(message)
      setSandboxState('error')
    } finally {
      sandboxBusy.current = false
    }
  }, [refreshAudit, refreshOnboarding, u])
  useEffect(() => {
    if (isTryEntry()) void startSandbox(true)
  }, [startSandbox])
  function closeOnboarding() {
    if (kitchen) skipOnboardingFor(kitchen)
    bumpSkip((n) => n + 1)
  }
  const caps = useTalkPhotoAvailable()
  const talk = useTalk()
  useLiveWarm(caps.talk && !talk.session && view === 'order' && !!savedKeys.agentKey) // HOOK: the idle /api/live socket, ready before the tap
  const orbRef = useRef<HTMLButtonElement>(null)
  const [layout, setLayout] = useState<VoiceLayout>(() => {
    try {
      return localStorage.getItem('valio-aimo-voice-layout') === 'thread' ? 'thread' : 'orb'
    } catch {
      return 'orb'
    }
  })
  function toggleLayout() {
    chooseLayout(layout === 'orb' ? 'thread' : 'orb')
  }
  // Swipe up on the orb = voice only (big orb, thread hidden); swipe down = voice + text (thread, small orb).
  function chooseLayout(next: VoiceLayout) {
    setLayout(next)
    try {
      localStorage.setItem('valio-aimo-voice-layout', next)
    } catch {
      // storage blocked: remembered for this page only
    }
  }
  const live = useLive(
    talk.session,
    {
      // Live words: a partial line is replaced until it's final (a dot marks the reply being formed).
      onTranscript: (role, said, final) =>
        setThread((t) => {
          const last = t[t.length - 1]
          const kind = role === 'user' ? 'user' : 'agent'
          if (last && last.kind === kind && last.partial) return [...t.slice(0, -1), { ...last, text: said, partial: !final }]
          return [...t, { id: ++nextId.current, kind, text: said, partial: !final }]
        }),
      onResult: (r) => {
        setResult(r)
        push({ kind: 'res', res: r, date: r.requested_date ?? date })
      },
      onError: (message) => push({ kind: 'error', text: message, reask: null }),
    },
    orbRef,
    { denied: u.talk.denied, closed: u.talk.closed },
  )
  function startVoice() {
    voice.cancel() // the mic is the conversation's now
    talk.open()
  }
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
    onboarding.refresh()
    keysDialog.current?.close()
    refreshAudit()
  }

  // A new request, or (with `to`) the answer to the question the agent just asked.
  async function ask(words: string, to?: string, when?: string) {
    if (!words.trim()) return
    push({ kind: 'user', text: words.trim() })
    if (!to) lastRequest.current = words.trim()
    setText('')
    setRunning(true)
    setAnnounce(u.ask.announce)
    try {
      phaseLine.reset()
      const have = pantry.current.length ? { have: pantry.current } : {}
      const input = to
        ? { text: '', follow_up: { to, answer: words.trim() }, ...have }
        : { text: words.trim(), ...(when ? { requested_date: when } : {}), ...have } // the day comes from the words, or the agent asks
      const res = await askAgentStream(input, (p) =>
        phaseLine.push(c.UI.progress.phases[p.phase] ?? p.text),
      )
      await phaseLine.settle() // let the last step be read before the answer replaces it
      if (res.requested_date) setDate(res.requested_date) // the fallback day for cards that don't carry one
      setResult(res)
      // The agent's line (the backend's one-sentence `speak`), then the decision card; a question is its own message.
      if (!res.question && res.speak) push({ kind: 'agent', text: res.speak })
      // The pantry counts for this order only: a menu card keeps it for its own re-plans, then it is cleared.
      const usedHave = res.intent === 'menu' && !res.question ? pantry.current : undefined
      push({ kind: 'res', res, date: res.requested_date ?? date, asked: lastRequest.current, have: usedHave })
      if (usedHave) pantry.current = []
      if (res.question) setAnnounce(c.question(res.question, res.decision?.reasons[0]))
    } catch (err) {
      const expired = !!to && err instanceof ApiError && err.status === 404
      if (expired) setResult(null) // the question is gone; "Ask again" re-sends the original request
      const message = expired ? u.question.expired : err instanceof Error && err.message === DROPPED ? u.progress.dropped : errorText(err)
      push({ kind: 'error', text: message, reask: expired ? lastRequest.current : null })
      setAnnounce(expired ? u.question.expired : '')
    } finally {
      setRunning(false)
      refreshAudit()
    }
  }

  // The bar's Send: voice on -> over the live socket; a pending question -> the answer; otherwise a new request.
  function send(words: string) {
    if (talk.session) {
      push({ kind: 'user', text: words })
      live.sendText(words)
      setText('')
      return
    }
    void ask(words, convo ?? undefined)
  }

  // "For how many guests?" answered inline: the words go into the box and the agent reads it again.
  function answerGuests(n: number) {
    if (convo) return void ask(String(n), convo)
    void ask(`${lastRequest.current.replace(/[.\s]*$/, '')}. ${u.question.guests(n)}`)
  }

  // "Not this one" / "Edit your request": the last request back in the field, cursor at the end.
  function retry() {
    setText(lastRequest.current)
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
    void ask(`${lastRequest.current} again`)
  }
  function leaveIt() {
    setResult(null)
    push({ kind: 'agent', text: u.question.leftAlone })
    setAnnounce(u.question.leftAlone)
  }

  function prefillCalendar(words: string) {
    setView('order')
    setText(words)
    requestAnimationFrame(() => {
      const f = field.current
      if (!f) return
      f.focus()
      f.setSelectionRange(f.value.length, f.value.length)
    })
  }

  function showPlannedCalendarMenu(plan: MenuRun, requestedDate: string, covers: number) {
    const planned: AskResponse = { ...plan, intent: 'menu', requested_date: requestedDate, date_source: 'request', covers }
    setView('order')
    setResult(planned)
    push({ kind: 'agent', text: c.UI.conv.cartNow(c.money(plan.cart_total_cents)) })
    push({ kind: 'res', res: planned, date: requestedDate, asked: plan.menu.dishes.map((dish) => dish.name).join(', ') })
    setAnnounce(c.UI.conv.cartNow(c.money(plan.cart_total_cents)))
    refreshAudit()
  }

  // The cart was re-planned: the agent's line above the card said the old total, so it is rewritten.
  function replanned(id: number, p: MenuRun) {
    setThread((t) => {
      const at = t.findIndex((x) => x.id === id)
      const before = t[at - 1]
      if (at < 1 || !before || before.kind !== 'agent') return t
      return t.map((x, i) => (i === at - 1 ? { ...x, text: u.conv.cartNow(c.money(p.cart_total_cents)) } : x))
    })
  }
  const empty = thread.length === 0 && !running
  const lastRes = [...thread].reverse().find((it) => it.kind === 'res')?.id ?? null
  const [opened, setOpened] = useState<Set<number>>(new Set()) // earlier cards the chef reopened

  // One response in the thread. Only the newest is a full, actionable card; earlier ones fold to their status and
  // headline (kept mounted, so a card's own state, e.g. an approval just made, survives), tap to reopen. A question
  // is the agent's message with its one-tap answers; an earlier one is just the message.
  function renderRes(it: Extract<Item, { kind: 'res' }>, latest: boolean) {
    const r = it.res
    if (r.question) {
      const said = c.question(r.question, r.decision?.reasons[0])
      if (!latest)
        return (
          <p key={it.id} className="msg msg-agent">
            {said}
          </p>
        )
      const to = r.conversation_id ?? null
      const guests = r.intent === 'menu' && r.covers == null && /guest|hengel|vier/i.test(r.question)
      return guests ? (
        <GuestsQuestion key={it.id} question={r.question} onAnswer={answerGuests} busy={running} />
      ) : (
        <Question
          key={it.id}
          question={r.question}
          more={r.intent === 'unclear'}
          reason={r.decision?.reasons[0] ?? null}
          answerable={!!to}
          busy={running}
          onAnswer={(words) => to && void ask(words, to)}
          onAgain={orderAgain}
          onLeave={leaveIt}
          onEdit={retry}
        />
      )
    }
    const isMenu = r.intent === 'menu' && 'lines' in r
    const isRun = r.intent === 'order' && 'lines' in r
    if (!isMenu && !isRun) return null
    const urgent = r.urgent_options
    const after = urgent && urgent.length > 0 ? <UrgentOptions options={urgent} /> : null
    const open = latest || opened.has(it.id)
    const status =
      isRun && r.order
        ? { confirmed: u.status.ordered, pending_approval: u.status.yourCall, refused: u.status.notOrdered, rejected: u.status.rejected }[r.order.status]
        : isRun
          ? r.decision.outcome === 'DECLINE' ? u.status.notOrdered : u.status.yourCall
          : u.status.ready
    const what = isRun ? r.request.summary : c.money(r.cart_total_cents)
    return (
      <div key={it.id} className="conv-card">
        {!open && (
          <button type="button" className="conv-fold" onClick={() => setOpened((o) => new Set(o).add(it.id))}>
            <span className="conv-fold-what">{u.conv.folded(status ?? '', what)}</span>
            <span className="accent-text">{u.conv.open}</span>
          </button>
        )}
        <div hidden={!open}>
          {isMenu ? (
            <MenuResult plan={r} covers={r.covers ?? null} requestedDate={it.date} onAction={refreshAudit} onBusy={setDeciding} onAnnounce={setAnnounce} after={after} menuText={it.asked} have={it.have} onReplanned={(p) => replanned(it.id, p)} />
          ) : (
            <RunResult
              run={r}
              requestedDate={it.date}
              onAction={refreshAudit}
              onBusy={setDeciding}
              onAnnounce={setAnnounce}
              onRetry={retry}
              onHistory={() => setView('history')}
              onPlain={(need) => void ask(`${lastRequest.current} (regular, not ${need})`, undefined, it.date)} // the backend reads "regular" / "not gluten…" as the buyer's own words
              onAskFor={(next) => void ask(next, undefined, it.date)} // same delivery day as the result it came from
              after={after}
            />
          )}
        </div>
      </div>
    )
  }

  if (sandboxState === 'setting-up') {
    return (
      <main className="try-setup">
        <p className="try-setup-line" role="status">{u.sandbox.settingUp}</p>
      </main>
    )
  }
  if (sandboxState === 'error') {
    return (
      <main className="try-setup">
        <div className="problem" role="alert">
          <strong>{u.sandbox.failed}</strong>
          {sandboxError}
          <div className="actions">
            <button type="button" className="btn" onClick={() => void startSandbox(isTryEntry())}>{u.sandbox.retry}</button>
          </div>
        </div>
      </main>
    )
  }

  return (
    <>
      <header className="top">
        <div className="top-bar">
          <div className="top-bar-in">
            <span className="brand">
              <DoorGlyph /> Front Door
            </span>
            <span className="brand-for">{view === 'valio' ? 'Valio Aimo' : buyer ? buyerLabel(buyer) : ''}</span>
            <HeaderMenu onSwitchLang={onSwitchLang} />
          </div>
        </div>
        <div className="top-nav">
          <nav aria-label={u.nav.main}>
            {!needsSetup &&
              (['order', 'history', 'kitchen', 'rules'] as const).map((v) => (
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
          </nav>
        </div>
      </header>

      <dialog ref={keysDialog} className="sheet" aria-labelledby="keys-dialog-title">
        <KeysForm key={savedKeys.agentKey} titleId="keys-dialog-title" title={u.keys.title} onSaved={keysSaved} onNewSandbox={() => void startSandbox(false, true)} onCancel={() => keysDialog.current?.close()} />
        {!adminKey && <ValioLink onOpen={openAdmin} />}
      </dialog>
      <dialog ref={adminDialog} className="sheet" aria-labelledby="admin-dialog-title">
        <AdminKeyForm onSaved={adminSaved} onCancel={() => adminDialog.current?.close()} />
      </dialog>

      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      <main>
        {MOCK && (
          <p className="mock" role="note">
            <strong>{u.mock.title}</strong> {u.mock.body}
          </p>
        )}
        {fromLink === 'saved' && (
          <p className="note banner" role="status">
            {u.keys.fromLink}{' '}
            <button type="button" className="link accent inline" onClick={() => setFromLink(null)}>
              {u.keys.ok}
            </button>
          </p>
        )}
        {fromLink === 'invalid' && (
          <div className="problem banner" role="alert">
            <strong>{u.keys.linkInvalid}</strong>
            {u.keys.linkKept}{' '}
            <button type="button" className="link accent inline" onClick={() => setFromLink(null)}>
              {u.keys.ok}
            </button>
          </div>
        )}
        {fromLink === 'confirm' && linkKitchen === undefined && (
          <p className="note banner" role="status">
            {u.keys.linkChecking}
          </p>
        )}
        {fromLink === 'confirm' && linkKitchen !== undefined && (
          <div className="banner" role="alertdialog" aria-labelledby="link-keys-q">
            <p id="link-keys-q">{u.keys.switchQ(linkKitchen ? buyerLabel(linkKitchen) : null)}</p>
            <div className="actions">
              <button type="button" className="btn" onClick={() => answerLink(true)}>
                {u.keys.switchTo}
              </button>
              <button type="button" className="btn plain" onClick={() => answerLink(false)}>
                {u.keys.keepCurrent}
              </button>
            </div>
          </div>
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
            <section hidden={view !== 'order'} aria-label={u.nav.order}>
              <h1 className="sr-only">{u.nav.order}</h1>
              {/* HOOK: which kitchen this device is signed in as (KitchenChip.tsx, useKitchen.ts) */}
              <KitchenChip kitchen={kitchen} onSwitch={() => keysDialog.current?.showModal()} />
              {/* HOOK: the calendar opens from the chat screen and returns planned menus to this thread. */}
              {!onboardingOpen && <Calendar onPrefill={prefillCalendar} onMenuPlanned={showPlannedCalendarMenu} />}
              {onboardingOpen ? (
                <Onboarding
                  onDone={() => {
                    onboarding.refresh()
                    closeOnboarding()
                  }}
                  onSkip={closeOnboarding}
                  mic={micOn ? (append) => <DictationMic onText={append} /> : undefined}
                />
              ) : (
                <Conversation
                  voiceOn={!!talk.session}
                  layout={layout}
                  onToggle={toggleLayout}
                  bigOrb={<Orb state={live.state} size="big" label={u.conv.orbToThread} onToggle={toggleLayout} onSwipe={(dir) => chooseLayout(dir === 'up' ? 'orb' : 'thread')} orbRef={orbRef} />}
                  smallOrb={<Orb state={live.state} size="small" label={u.conv.orbToBig} onToggle={toggleLayout} onSwipe={(dir) => chooseLayout(dir === 'up' ? 'orb' : 'thread')} orbRef={orbRef} />}
                  status={
                    <p role="status" className={live.state === 'error' ? 'bad' : undefined}>
                      {live.muted ? u.conv.muted : live.state === 'connecting' ? u.talk.connecting : (live.tool ?? u.talk.state[live.state])}
                    </p>
                  }
                  thread={
                    <>
                      {empty && (
                        <div className="conv-start">
                          {waiting !== null && <p className="greeting">{u.greeting(partOfDay(), approver, waiting)}</p>}
                          <p className="try">{MOCK ? u.ask.tryDemo : u.ask.try}</p>
                          <div className="conv-suggest">
                            {c.TRY.map((t) => (
                              <button key={t} type="button" className="chip" onClick={() => setText(t)}>
                                {t}
                              </button>
                            ))}
                          </div>
                          <Recent groups={groups.slice(0, 3)} onOpen={() => setView('history')} />
                        </div>
                      )}
                      {thread.map((it) =>
                        it.kind === 'user' ? (
                          <p key={it.id} className={`msg msg-user${it.partial ? ' msg-partial' : ''}`}>
                            {it.text}
                          </p>
                        ) : it.kind === 'agent' ? (
                          <p key={it.id} className={`msg msg-agent${it.partial ? ' msg-partial' : ''}`}>
                            {it.text}
                            {it.partial && <span className="msg-dot" aria-hidden="true" />}
                          </p>
                        ) : it.kind === 'error' ? (
                          <div key={it.id} className="problem" role="alert">
                            <strong>{u.failed}</strong>
                            {it.text}
                            {it.reask && (
                              <div className="actions">
                                <button type="button" className="btn" onClick={() => void ask(it.reask!)} disabled={running}>
                                  {u.question.reask}
                                </button>
                              </div>
                            )}
                          </div>
                        ) : (
                          renderRes(it as Extract<Item, { kind: 'res' }>, it.id === lastRes)
                        ),
                      )}
                      {running && (
                        <div className="working" role="status" aria-label={u.progress.aria}>
                          {/* Re-keyed per phase, so each step fades in; the status region reads each step out politely. */}
                          <p key={phaseLine.phase ?? 'start'} className="phase">
                            {phaseLine.phase ?? u.progress.phases.understanding}
                          </p>
                          <div className="working-bar" aria-hidden="true" />
                        </div>
                      )}
                    </>
                  }
                  composer={
                    <>
                      {micOn && !talk.session && <VoiceStatus voice={voice} />}
                      <Composer
                        voiceOn={!!talk.session}
                        text={text}
                        setText={setText}
                        onSend={send}
                        placeholder={talk.session ? u.conv.voicePlaceholder : convo ? u.conv.answerHere : u.conv.placeholder}
                        busy={running}
                        photo={
                          caps.photo ? (
                            <PhotoButton
                              variant="icon"
                              disabled={running || deciding}
                              onRead={(words) => send(words)}
                              onPantry={(have, message) => {
                                pantry.current = have
                                push({ kind: 'agent', text: message ?? u.conv.pantryRead(have.join(', ')) })
                              }}
                            />
                          ) : null
                        }
                        mic={micOn ? <MicButton voice={voice} disabled={running || deciding} /> : null}
                        onVoice={caps.talk ? startVoice : null}
                        muted={live.muted}
                        onMute={() => live.setMuted((m) => !m)}
                        onEnd={talk.end}
                        fieldRef={field}
                      />
                    </>
                  }
                />
              )}
            </section>

            <section hidden={view !== 'rules'} aria-label={u.nav.rules}>
              <Rules
                refreshKey={auditKey}
                onAction={refreshAudit}
                onAnnounce={setAnnounce}
              />
            </section>

            {/* HOOK: the Kitchen tab (Kitchen.tsx): onboarding on demand, what I know with sources, the kitchen's history */}
            <section hidden={view !== 'kitchen'} aria-label={u.nav.kitchen}>
              {view === 'kitchen' && <Kitchen refreshKey={auditKey} />}
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
  question: string; more: boolean; reason: Reason | null; answerable: boolean; busy: boolean
  onAnswer: (words: string) => void; onAgain: () => void; onLeave: () => void; onEdit: () => void
}) {
  const c = useCopy()
  const u = c.UI
  const heading = useRef<HTMLHeadingElement>(null)
  const again = p.reason?.facts.minutes_ago != null
  // "For which delivery day?": the next days as one-tap answers (sent as "20.11.", which the backend reads exactly).
  const askingDay = p.answerable && /which delivery day/i.test(p.question)
  const days = askingDay ? nextDays(6) : []
  // "Which one did you mean: 1) A; 2) B; 3) C? Or say it more precisely.": the options as one-tap answers ("2").
  const options = p.answerable ? (/^Which one did you mean: (.+)\? Or say it more precisely\.?$/.exec(p.question)?.[1].split('; ').map((o) => o.replace(/^\d\)\s*/, '')) ?? []) : []
  useEffect(() => heading.current?.focus(), []) // the question comes into view; the answer goes in the bar below
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
      ) : null}
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

function KeyIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="15" r="4" />
      <path d="M11 12l9-9M16 7l3 3M14 9l2 2" />
    </svg>
  )
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {off && <path d="M4 4l16 16" />}
    </svg>
  )
}

// Two keys in one nested card: a soft outer shell, a white card inside. Keys are trimmed on save (pasted spaces and newlines break requests).
function KeysForm({
  title, titleId, intro, submitLabel, onSaved, onNewSandbox, onCancel,
}: { title: string; titleId?: string; intro?: string; submitLabel?: string; onSaved: () => void; onNewSandbox?: () => void; onCancel?: () => void }) {
  const k = useCopy().UI.keys
  const [keys, setDraft] = useState<ApiKeys>(getKeys)
  const ready = !!keys.agentKey.trim() && !!keys.approverKey.trim()
  function save(e: FormEvent) {
    e.preventDefault()
    if (!ready) return
    setKeys({ ...keys, agentKey: keys.agentKey.trim(), approverKey: keys.approverKey.trim() })
    onSaved()
  }
  return (
    <form className="setup keys-shell" onSubmit={save}>
      <div className="keys-card">
        <div className="keys-head">
          <span className="keys-badge">
            <KeyIcon />
          </span>
          <h1 className="title" id={titleId}>
            {title}
          </h1>
          {intro && <p className="note">{intro}</p>}
          <p className="note small">{k.tip}</p>
        </div>
        <SecretField id="agent-key" label={k.agent} help={k.agentHelp} value={keys.agentKey} onChange={(v) => setDraft({ ...keys, agentKey: v })} />
        <SecretField id="approver-key" label={k.approver} help={k.approverHelp} value={keys.approverKey} onChange={(v) => setDraft({ ...keys, approverKey: v })} />
        <div className="keys-actions">
          <button type="submit" className="btn" disabled={!ready}>
            {submitLabel ?? k.save}
          </button>
          {onNewSandbox && (
            <button type="button" className="btn plain" onClick={onNewSandbox}>
              {k.newSandbox}
            </button>
          )}
          {onCancel && (
            <button type="button" className="btn plain" onClick={onCancel}>
              {k.cancel}
            </button>
          )}
        </div>
      </div>
    </form>
  )
}

function SecretField({ id, label, help, value, onChange }: { id: string; label: string; help: string; value: string; onChange: (v: string) => void }) {
  const k = useCopy().UI.keys
  const [shown, setShown] = useState(false)
  return (
    <div className="field keys-field">
      <label htmlFor={id}>{label}</label>
      <div className="secret keys-secret">
        <span className="keys-lead">
          <KeyIcon />
        </span>
        <input
          id={id}
          type={shown ? 'text' : 'password'}
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          aria-describedby={`${id}-help`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className="secret-toggle" aria-pressed={shown} aria-controls={id} aria-label={shown ? k.hide : k.show} title={shown ? k.hide : k.show} onClick={() => setShown((s) => !s)}>
          <EyeIcon off={shown} />
        </button>
      </div>
      <p className="field-help" id={`${id}-help`}>
        {help}
      </p>
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
