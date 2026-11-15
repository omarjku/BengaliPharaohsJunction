import { useEffect, useRef, useState } from 'react'
import { getKeys, MOCK, VOICE_READY } from './api'
import { confirmInterview, getInterviewNext, type InterviewAnswer, type InterviewPreview, type InterviewValue } from './kitchenEditApi'
import { KITCHEN_EDIT_COPY, type KitchenEditCopy } from './kitchenEditCopy'
import { useCopy } from './i18n'
import { Orb } from './Orb'
import { errorText } from './format'
import { useTalk, useTalkPhotoAvailable } from './useTalk'
import { useLive, type LiveState } from './useLive'
import { voiceSupported } from './useVoice'
import './InterviewCard.css'

type Caption = { role: 'user' | 'agent'; text: string; final: boolean }

const emptyValue = (value: InterviewValue) => {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  return JSON.stringify(value)
}

function valueText(value: InterviewValue): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) return value.join(', ')
  if (Array.isArray(value)) return value.map((item) => `${item.weekday}: ${item.lines.map((line) => line.text).join(', ')}`).join('; ')
  return JSON.stringify(value)
}

function editedValue(original: InterviewValue, text: string): InterviewValue {
  if (typeof original === 'number') {
    const value = Number(text)
    return Number.isFinite(value) ? value : original
  }
  if (typeof original === 'string') return text
  if (Array.isArray(original) && original.every((item) => typeof item === 'string'))
    return text.split(/[,\n]/).map((item) => item.trim()).filter(Boolean)
  try {
    return JSON.parse(text) as InterviewValue
  } catch {
    return original
  }
}

function liveLabel(state: LiveState, t: KitchenEditCopy['interview']): string {
  if (state === 'connecting') return t.connecting
  if (state === 'thinking') return t.thinking
  if (state === 'speaking') return t.speaking
  if (state === 'error') return t.failed
  return t.listening
}

export function InterviewCard() {
  const c = useCopy()
  const t = KITCHEN_EDIT_COPY[c.LANG].interview
  const { agentKey, approverKey } = getKeys()
  const hasAgent = MOCK || !!agentKey
  const hasApprover = MOCK || !!approverKey
  const caps = useTalkPhotoAvailable()
  const talk = useTalk()
  const orbRef = useRef<HTMLButtonElement>(null)
  const [captions, setCaptions] = useState<Caption[]>([])
  const [preview, setPreview] = useState<InterviewPreview | null>(null)
  const [previewValues, setPreviewValues] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState(false)
  const [textMode, setTextMode] = useState(false)
  const [textQuestion, setTextQuestion] = useState<{ topic: InterviewAnswer['topic']; question: string } | null>(null)
  const [textAnswer, setTextAnswer] = useState('')
  const [textAnswers, setTextAnswers] = useState<InterviewAnswer[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const endRef = useRef(talk.end)
  endRef.current = talk.end

  const canVoice = hasAgent && caps.talk && VOICE_READY && voiceSupported()
  const live = useLive(
    talk.session,
    {
      onTranscript: (role, text, final) => setCaptions((current) => {
        const last = current[current.length - 1]
        if (last && last.role === role && !last.final) return [...current.slice(0, -1), { role, text, final }]
        return [...current, { role, text, final }]
      }),
      onResult: () => {},
      onWarning: (message) => setError(message),
      onInterviewPreview: (next) => {
        setPreview(next)
        setPreviewValues(Object.fromEntries(next.proposed.map((item) => [item.id, emptyValue(item.value)])))
        setTextMode(false)
        setError(null)
        endRef.current()
      },
      onError: (message) => setError(message),
      onSessionEnded: (message) => {
        setError(message)
        endRef.current()
      },
    },
    orbRef,
    { denied: t.failed, closed: t.failed },
    'interview',
  )

  useEffect(() => () => endRef.current(), [])

  async function startText() {
    setTextMode(true)
    setPreview(null)
    setSaved(false)
    setError(null)
    setTextAnswer('')
    setTextAnswers([])
    setBusy(true)
    try {
      const next = await getInterviewNext([])
      if (next.done) showPreview(next.preview)
      else setTextQuestion({ topic: next.topic, question: next.question })
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  async function submitText(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!textQuestion || !textAnswer.trim()) return
    const answers = [...textAnswers, { topic: textQuestion.topic, text: textAnswer.trim() }]
    setTextAnswers(answers)
    setTextAnswer('')
    setBusy(true)
    setError(null)
    try {
      const next = await getInterviewNext(answers)
      if (next.done) showPreview(next.preview)
      else setTextQuestion({ topic: next.topic, question: next.question })
    } catch (err) {
      setError(errorText(err) || t.textFailed)
    } finally {
      setBusy(false)
    }
  }

  function showPreview(next: InterviewPreview) {
    setPreview(next)
    setPreviewValues(Object.fromEntries(next.proposed.map((item) => [item.id, emptyValue(item.value)])))
    setTextQuestion(null)
    setTextMode(false)
  }

  async function save() {
    if (!preview || !hasApprover) return
    setBusy(true)
    setError(null)
    try {
      const answers = Object.fromEntries(preview.proposed.map((item) => [item.id, editedValue(item.value, previewValues[item.id] ?? emptyValue(item.value))]))
      await confirmInterview(answers)
      setSaved(true)
      setEditing(false)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (!hasAgent) {
    return (
      <section className="answer kitchen-edit-card interview-card">
        <h2 className="title">{t.title}</h2>
        <p className="note">{t.intro}</p>
        <p className="interview-note" role="status">{t.noAgent}</p>
      </section>
    )
  }

  return (
    <section className="answer kitchen-edit-card interview-card" aria-labelledby="interview-title">
      <h2 id="interview-title" className="title">{t.title}</h2>
      <p className="note">{t.intro}</p>

      {!preview && !textMode && (
        <div className="actions">
          {canVoice && (
            <button type="button" className="btn" onClick={() => (talk.session ? talk.end() : talk.open())}>
              {talk.session ? t.stop : t.startVoice}
            </button>
          )}
          <button type="button" className="btn plain" onClick={startText} disabled={busy}>
            {t.startText}
          </button>
        </div>
      )}

      {canVoice && talk.session && !preview && (
        <div className="interview-live">
          <div className="interview-orb-row">
            <Orb state={live.state} size="small" label={t.stop} onToggle={talk.end} onSwipe={() => {}} orbRef={orbRef} />
            <span className="quiet">{liveLabel(live.state, t)}</span>
          </div>
          <div className="interview-captions" aria-live="polite" aria-label={t.captions}>
            {captions.slice(-4).map((caption, index) => (
              <p key={`${caption.role}-${index}`} className={`interview-caption interview-caption-${caption.role} ${caption.final ? '' : 'interview-caption-partial'}`}>
                <span>{caption.role === 'agent' ? t.agentLabel : t.youLabel}</span>{caption.text}
              </p>
            ))}
          </div>
        </div>
      )}

      {textMode && !preview && (
        <div className="interview-text-mode">
          <p className="note">{t.textIntro}</p>
          {textQuestion && (
            <form className="interview-form" onSubmit={submitText}>
              <label className="field">
                <span>{t.questionLabel}</span>
                <strong>{textQuestion.question}</strong>
              </label>
              <label className="field">
                <span>{t.answerLabel}</span>
                <input value={textAnswer} onChange={(event) => setTextAnswer(event.target.value)} placeholder={t.answerPlaceholder} autoFocus />
              </label>
              <div className="actions">
                <button type="submit" className="btn" disabled={busy || !textAnswer.trim()}>{busy ? t.sending : t.send}</button>
                <button type="button" className="btn plain" onClick={() => setTextMode(false)} disabled={busy}>{t.stop}</button>
              </div>
            </form>
          )}
          {busy && !textQuestion && <p className="quiet" role="status">{t.sending}</p>}
        </div>
      )}

      {preview && (
        <div className="interview-preview">
          <div>
            <h3 className="title">{t.previewTitle}</h3>
            <p className="note">{t.previewIntro}</p>
          </div>
          {preview.proposed.length ? (
            <div className="interview-proposed">
              {preview.proposed.map((item) => (
                <label className="field" key={item.id}>
                  <span>{item.question}</span>
                  {editing ? (
                    <textarea value={previewValues[item.id] ?? ''} onChange={(event) => setPreviewValues((values) => ({ ...values, [item.id]: event.target.value }))} />
                  ) : (
                    <strong className="interview-value">{valueText(item.value)}</strong>
                  )}
                </label>
              ))}
            </div>
          ) : <p className="quiet">{t.emptyPreview}</p>}
          <div className="actions">
            <button type="button" className="btn plain" onClick={() => setEditing((value) => !value)} disabled={busy}>
              {editing ? t.doneEditing : t.edit}
            </button>
            <button type="button" className="btn" onClick={save} disabled={busy || !hasApprover || !preview.proposed.length}>
              {busy ? t.confirming : t.confirm}
            </button>
          </div>
          {!hasApprover && <p className="interview-note" role="status">{t.noApprover}</p>}
          {saved && <p className="interview-success" role="status">{t.saved}</p>}
        </div>
      )}

      {error && <p className="interview-error" role="alert">{error}</p>}
    </section>
  )
}
