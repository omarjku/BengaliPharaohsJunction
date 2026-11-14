// First-run onboarding: the chef tells the agent about the kitchen, as guidance (never rules). Either one box of free
// text (typed, or dictated through the `mic` slot) that Gemini reads into a preview the chef edits and confirms, or
// the questions one at a time. Always skippable. Saving needs the approver key (a human sets up the kitchen).
// Mount: <Onboarding onDone={…} onSkip={…} /> when useOnboarded() (onboardingApi.ts) says false.
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { MOCK, getKeys } from './api'
import { type AnswerValue, type Question, OnboardingError, getOnboarding, previewAbout, saveAnswers } from './onboardingApi'
import { type OnboardingCopy, useOnboardingCopy } from './onboardingCopy'
import './Onboarding.css'

type Mode = 'start' | 'tell' | 'preview' | 'steps' | 'review' | 'saved'
type Answers = Record<string, AnswerValue>
type Props = {
  onDone: () => void
  onSkip: () => void
  // Dictation slot: Room 4 passes its mic, which calls `append` with what was heard.
  mic?: (append: (text: string) => void) => ReactNode
}

const empty = (v: AnswerValue | undefined) =>
  v === undefined || v === '' || (Array.isArray(v) && v.length === 0) || (typeof v === 'object' && !Array.isArray(v) && !v.city)

export function Onboarding({ onDone, onSkip, mic }: Props) {
  const t = useOnboardingCopy()
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>('start')
  const [answers, setAnswers] = useState<Answers>({})
  const [about, setAbout] = useState('')
  const [unclear, setUnclear] = useState<string[]>([])
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const heading = useRef<HTMLHeadingElement>(null)
  const hasAgent = MOCK || !!getKeys().agentKey // mock mode needs no keys
  const hasApprover = MOCK || !!getKeys().approverKey

  function load() {
    setLoadError(null)
    getOnboarding()
      .then((o) => {
        setQuestions(o.questions)
        setAnswers(Object.fromEntries(o.questions.filter((q) => !empty(q.answer)).map((q) => [q.id, q.answer as AnswerValue])))
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : t.loadFailed))
  }
  useEffect(load, []) // eslint-disable-line react-hooks/exhaustive-deps -- load once on mount
  useEffect(() => heading.current?.focus(), [mode, step]) // screen readers hear each new step

  const set = (id: string, v: AnswerValue) => {
    setAnswers((a) => ({ ...a, [id]: v }))
    setFieldErrors((f) => ({ ...f, [id]: '' }))
  }

  async function read() {
    setBusy(true)
    setError(null)
    try {
      const p = await previewAbout(about.trim())
      setAnswers((a) => ({ ...a, ...Object.fromEntries(p.proposed.map((x) => [x.id, x.value])) }))
      setUnclear(p.unclear)
      if (p.proposed.length === 0) setError(t.nothingRead)
      else setMode('preview')
    } catch (e) {
      setError(e instanceof OnboardingError && (e.status === 401 || e.status === 403) ? t.noApprover : (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    const chosen = Object.fromEntries(Object.entries(answers).filter(([, v]) => !empty(v)))
    if (Object.keys(chosen).length === 0) return setError(t.nothingToSave)
    setBusy(true)
    setError(null)
    try {
      await saveAnswers(chosen)
      setMode('saved')
    } catch (e) {
      if (e instanceof OnboardingError) {
        setFieldErrors(e.errors)
        setError(e.status === 401 || e.status === 403 ? t.noApprover : e.message)
      } else setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!hasAgent) return <Frame t={t} headingRef={heading}><p className="ob-note" role="status">{t.noAgent}</p><SkipButton t={t} onSkip={onSkip} /></Frame>
  if (loadError) return <Frame t={t} headingRef={heading}><p className="ob-note bad" role="alert">{t.loadFailed} {loadError}</p><div className="ob-actions"><button className="btn" type="button" onClick={load}>{t.retry}</button><SkipButton t={t} onSkip={onSkip} /></div></Frame>
  if (!questions) return <Frame t={t} headingRef={heading}><p className="quiet" role="status">…</p></Frame>

  const approverNote = !hasApprover && <p className="ob-note" role="note">{t.noApprover}</p>

  if (mode === 'saved')
    return (
      <Frame t={t} headingRef={heading}>
        <p role="status">{t.saved}</p>
        <div className="ob-actions"><button className="btn" type="button" onClick={onDone}>{t.done}</button></div>
      </Frame>
    )

  if (mode === 'start')
    return (
      <Frame t={t} headingRef={heading}>
        <p className="quiet">{t.welcome}</p>
        {approverNote}
        <div className="ob-start">
          <button className="ob-path" type="button" onClick={() => setMode('tell')}>
            <span className="ob-path-title">{t.tellChoice}</span>
            <span className="ob-path-help">{t.tellHelp}</span>
          </button>
          <button className="ob-path" type="button" onClick={() => { setStep(0); setMode('steps') }}>
            <span className="ob-path-title">{t.stepsChoice}</span>
          </button>
        </div>
        <SkipButton t={t} onSkip={onSkip} />
      </Frame>
    )

  if (mode === 'tell')
    return (
      <Frame t={t} headingRef={heading} sub={t.tellChoice}>
        {approverNote}
        <div className="field">
          <label htmlFor="ob-about">{t.aboutLabel}</label>
          <span className="field-help" id="ob-about-help">{t.tellHelp}</span>
          <textarea id="ob-about" className="ob-textarea" rows={5} maxLength={2000} value={about}
            aria-describedby="ob-about-help" placeholder={t.aboutPlaceholder} onChange={(e) => setAbout(e.target.value)} />
          {mic && <div className="ob-mic">{mic((text) => setAbout((a) => (a ? `${a} ${text}` : text)))}</div>}
        </div>
        {error && <p className="ob-note bad" role="alert">{error}</p>}
        <div className="ob-actions">
          <button className="btn" type="button" disabled={busy || !about.trim() || !hasApprover} onClick={read}>
            {busy ? t.reading : t.read}
          </button>
          <button className="btn plain" type="button" onClick={() => setMode('start')}>{t.back}</button>
        </div>
        <SkipButton t={t} onSkip={onSkip} />
      </Frame>
    )

  if (mode === 'steps') {
    const q = questions[step]
    const last = step === questions.length - 1
    return (
      <Frame t={t} headingRef={heading} sub={t.progress(step + 1, questions.length)}>
        <QuestionField t={t} q={q} value={answers[q.id]} error={fieldErrors[q.id]} onChange={(v) => set(q.id, v)} big />
        <div className="ob-actions">
          <button className="btn" type="button" onClick={() => (last ? setMode('review') : setStep(step + 1))}>
            {last ? t.review : t.next}
          </button>
          <button className="btn plain" type="button" onClick={() => (step === 0 ? setMode('start') : setStep(step - 1))}>{t.back}</button>
          {!last && <button className="btn plain" type="button" onClick={() => setStep(step + 1)}>{t.skipQuestion}</button>}
        </div>
        <SkipButton t={t} onSkip={onSkip} />
      </Frame>
    )
  }

  // preview (from free text) and review (after the steps): every answered question, editable, then one Save.
  const shown = questions.filter((q) => !empty(answers[q.id]) || fieldErrors[q.id])
  return (
    <Frame t={t} headingRef={heading} sub={t.previewTitle}>
      <p className="quiet">{t.previewHelp}</p>
      {approverNote}
      <div className="ob-list">
        {shown.map((q) => (
          <QuestionField key={q.id} t={t} q={q} value={answers[q.id]} error={fieldErrors[q.id]} onChange={(v) => set(q.id, v)} />
        ))}
      </div>
      {unclear.length > 0 && (
        <div className="ob-note" role="note">
          <p>{t.unclear}</p>
          <ul className="ob-unclear">{unclear.map((u) => <li key={u}>{u}</li>)}</ul>
        </div>
      )}
      {error && <p className="ob-note bad" role="alert">{error}</p>}
      <div className="ob-actions">
        <button className="btn" type="button" disabled={busy || !hasApprover} onClick={save}>{busy ? t.saving : t.save}</button>
        {mode === 'preview' && shown.length < questions.length && (
          <button className="btn plain" type="button" onClick={() => { setStep(0); setMode('steps') }}>{t.answerRest}</button>
        )}
      </div>
      <SkipButton t={t} onSkip={onSkip} />
    </Frame>
  )
}

function Frame({ t, headingRef, sub, children }: { t: OnboardingCopy; headingRef: React.RefObject<HTMLHeadingElement | null>; sub?: string; children: ReactNode }) {
  return (
    <section className="ob" aria-labelledby="ob-title">
      <h1 className="ob-title" id="ob-title" ref={headingRef} tabIndex={-1}>{t.title}</h1>
      {sub && <p className="ob-sub" aria-live="polite">{sub}</p>}
      {children}
    </section>
  )
}

function SkipButton({ t, onSkip }: { t: OnboardingCopy; onSkip: () => void }) {
  return <button className="btn plain ob-skip" type="button" onClick={onSkip}>{t.skip}</button>
}

// One question as a labelled control: large tap targets for choices, a list field for staples, City, region for
// location. Values go to the backend as it expects them (it validates and explains anything off).
function QuestionField({ t, q, value, error, onChange, big }: {
  t: OnboardingCopy; q: Question; value: AnswerValue | undefined; error?: string; onChange: (v: AnswerValue) => void; big?: boolean
}) {
  const id = `ob-q-${q.id}`
  const label = t.questions[q.id] ?? q.question
  const explain = t.explain[q.id]
  const helpId = `${id}-help`
  const errId = `${id}-err`
  const describedBy = [explain && helpId, error && errId].filter(Boolean).join(' ') || undefined
  const opt = (o: string) => t.options[o] ?? o
  const errorLine = error ? <p className="ob-error" id={errId} role="alert">{error}</p> : null
  const help = explain ? <p className="field-help" id={helpId}>{explain}</p> : null

  if (q.input === 'choice' || (q.input === 'multi' && q.options)) {
    const multi = q.input === 'multi'
    const picked = multi ? (Array.isArray(value) ? value : []) : typeof value === 'string' ? [value] : []
    const toggle = (o: string) => onChange(multi ? (picked.includes(o) ? picked.filter((x) => x !== o) : [...picked, o]) : o)
    return (
      <fieldset className={`ob-q${big ? ' big' : ''}`} aria-describedby={describedBy}>
        <legend className="ob-label">{label}</legend>
        {multi && <p className="field-help">{t.multiHelp}</p>}
        {help}
        <div className="ob-options" role={multi ? 'group' : 'radiogroup'} aria-label={label}>
          {q.options!.map((o) => (
            <button key={o} type="button" className="ob-option" onClick={() => toggle(o)}
              role={multi ? undefined : 'radio'} aria-checked={multi ? undefined : picked.includes(o)}
              aria-pressed={multi ? picked.includes(o) : undefined}>
              {opt(o)}
            </button>
          ))}
        </div>
        {errorLine}
      </fieldset>
    )
  }

  // Free text: staples as a comma list, location as "City, region", the rest as written.
  const text = Array.isArray(value) ? value.join(', ') : value && typeof value === 'object' ? [value.city, value.region].filter(Boolean).join(', ') : value == null ? '' : String(value)
  const parse = (s: string): AnswerValue => {
    if (q.input === 'multi') return s.split(',').map((x) => x.trim()).filter(Boolean)
    if (q.id === 'location') {
      const [city, ...rest] = s.split(',').map((x) => x.trim())
      return { city: city ?? '', region: rest.join(', ') || null }
    }
    return s
  }
  const placeholder = q.input === 'multi' ? t.listHelp : q.id === 'location' ? t.cityRegion : q.id === 'spend_comfort' ? t.spendHelp : undefined
  return (
    <div className={`field ob-q${big ? ' big' : ''}`}>
      <label className="ob-label" htmlFor={id}>{label}</label>
      {help}
      {q.input === 'multi' && <p className="field-help">{t.listHelp}</p>}
      <input id={id} className="ob-input" value={text} placeholder={placeholder} aria-describedby={describedBy}
        aria-invalid={!!error} inputMode={q.id === 'spend_comfort' ? 'decimal' : undefined}
        onChange={(e) => onChange(parse(e.target.value))} />
      {errorLine}
    </div>
  )
}
