import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, compileRules, getKeys, getMandate, MOCK, saveMandate } from './api'
import { errorText } from './format'
import { useCopy } from './i18n'
import type { CompileResult, Mandate } from './types'
import { WeeklyMenus } from './WeeklyMenus'

type Props = { refreshKey: number; onAction: () => void; onAnnounce: (text: string) => void }

// The chef's rules: read them in plain words, rewrite them in plain words, check what changes, then save.
// Compile never saves; saving needs every open question answered or skipped, and a second yes for anything looser.
// Saves carry the version the chef was looking at (If-Match), so nobody silently overwrites someone else's change.
export function Rules({ refreshKey, onAction, onAnnounce }: Props) {
  const c = useCopy()
  const t = c.UI.rules
  const approverKey = getKeys().approverKey
  const canRead = MOCK || Boolean(approverKey)
  const [current, setCurrent] = useState<Mandate | null | undefined>(undefined) // undefined = loading
  const [version, setVersion] = useState<string | null>(null) // the ETag of the rules on screen
  const [reload, setReload] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null) // null until the current rules prefill it
  const [proposal, setProposal] = useState<CompileResult | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [skipped, setSkipped] = useState<Set<number>>(new Set())
  const [busy, setBusy] = useState<'check' | 'save' | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false) // someone else saved first: the latest rules are shown
  const [saved, setSaved] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const confirmTitle = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoadError(null)
    if (!canRead) return
    getMandate().then(
      ({ mandate, etag }) => {
        if (cancelled) return
        setCurrent(mandate)
        setVersion(etag)
        setText((old) => old ?? (mandate ? c.ruleWords(mandate) : ''))
      },
      (e) => !cancelled && setLoadError(errorText(e)),
    )
    return () => {
      cancelled = true
    }
  }, [canRead, approverKey, refreshKey, reload, c])

  useEffect(() => {
    if (proposal || saved || conflict) heading.current?.focus()
  }, [proposal, saved, conflict])
  useEffect(() => {
    if (confirming) confirmTitle.current?.focus() // the "are you sure?" takes focus, so it's read and answered first
  }, [confirming])

  async function check(withText: string) {
    setBusy('check')
    setError(null)
    setSaved(null)
    setConflict(false)
    setConfirming(false)
    onAnnounce(t.readingAnnounce)
    try {
      const res = await compileRules(withText)
      setProposal(res)
      setAnswers({})
      setSkipped(new Set())
      onAnnounce(t.changesAnnounce(res.diff_from_current.length))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (text?.trim()) void check(text.trim())
  }

  // Answers go back into the rules with their question (an answer alone, like "yes", means nothing to the compiler),
  // and the rules are read again.
  function applyAnswers() {
    const added = Object.entries(answers)
      .filter(([i, a]) => a.trim() && !skipped.has(Number(i)))
      .map(([i, a]) => `${questions[Number(i)]?.question ?? ''} ${a.trim()}`.trim())
    const next = [text ?? '', ...added].join('\n').trim()
    setText(next)
    void check(next)
  }

  const questions = proposal?.open_questions ?? []
  const open = questions.map((_, i) => i).filter((i) => !skipped.has(i))
  const typed = open.some((i) => answers[i]?.trim())
  const looser = proposal?.diff_from_current.filter((ch) => ch.change === 'looser') ?? []
  // Looser changes first: they're the ones that need a second look.
  const changes = [...(proposal?.diff_from_current ?? [])].sort((a, b) => Number(b.change === 'looser') - Number(a.change === 'looser'))
  const unreadable = !!proposal?.used_fallback // the compiler couldn't read the text: nothing to save

  async function save() {
    if (!proposal || open.length || unreadable) return
    if (looser.length && !confirming) {
      setConfirming(true)
      return
    }
    setBusy('save')
    setError(null)
    try {
      const keep = proposal.proposed_mandate.open_questions.filter((_, i) => !skipped.has(i))
      const res = await saveMandate(
        { ...proposal.proposed_mandate, open_questions: keep },
        proposal.diff_from_current.some((ch) => ch.needs_confirmation),
        version,
      )
      setCurrent(res.mandate)
      setVersion(res.etag)
      setText(c.ruleWords(res.mandate))
      setProposal(null)
      setConfirming(false)
      setSaved(t.saved(res.changes.length))
      onAnnounce(t.savedAnnounce)
      onAction()
    } catch (err) {
      setConfirming(false)
      if (err instanceof ApiError && err.status === 412) {
        // Someone saved first. Show their rules; the chef's text stays in the box to check again.
        setProposal(null)
        setConflict(true)
        setReload((n) => n + 1)
        onAnnounce(t.conflict)
      } else setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  if (!canRead) return <p className="problem">{t.needKey}</p>

  return (
    <>
      <div className="ask">
        <h1 className="title">{t.title}</h1>
        <p className="note">{t.intro}</p>
      </div>
      {conflict && (
        <div className="problem" role="status">
          <strong ref={heading} tabIndex={-1}>
            {t.conflict}
          </strong>
          {t.conflictSub}
        </div>
      )}
      {loadError && (
        <div className="problem" role="alert">
          <strong>{t.loadFailed}</strong>
          {loadError}
        </div>
      )}
      {current === undefined && !loadError && <p className="note empty">{t.loading}</p>}
      {current === null && <p className="note empty">{t.none}</p>}
      {current && (
        <ul className="rules">
          {c.ruleLines(current).map((r, i) => (
            <li key={i}>
              <p>{r.text}</p>
              {r.said && <p className="quiet small">{t.youSaid(r.said)}</p>}
            </li>
          ))}
        </ul>
      )}

      {text !== null && (
        <form className="ask section-gap" onSubmit={submit}>
          <label className="ask-label" htmlFor="rules-text">
            {t.tell}
          </label>
          <p className="note">{t.tellHelp}</p>
          <textarea
            id="rules-text"
            className="ask-field rules-field"
            rows={6}
            maxLength={4000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t.placeholder}
            required
          />
          <div className="ask-row">
            <p className="note">{t.nothingChanges}</p>
            <button type="submit" className="btn" disabled={busy !== null || !text.trim()}>
              {busy === 'check' ? t.reading : t.check}
            </button>
          </div>
        </form>
      )}

      {busy === 'check' && (
        <div className="working">
          <p>{t.readingLong}</p>
          <div className="working-bar" aria-hidden="true" />
        </div>
      )}
      {error && (
        <div className="problem" role="alert">
          <strong>{c.UI.failed}</strong>
          {error}
        </div>
      )}

      {saved && !proposal && (
        <section className="answer" aria-label={t.savedStatus}>
          <p className="status good">{t.savedStatus}</p>
          <h2 ref={heading} tabIndex={-1} className="answer-text">
            {saved}
          </h2>
          <p className="answer-sub">{t.savedSub}</p>
        </section>
      )}

      {proposal && (
        <section className="answer" aria-label={t.notSaved}>
          <p className="status neutral">{t.notSaved}</p>
          <h2 ref={heading} tabIndex={-1} className="answer-text">
            {t.changes(proposal.diff_from_current.length)}
          </h2>
          {proposal.injection_flagged && (
            <div className="problem">
              <strong>{t.injectionTitle}</strong>
              {t.injectionBody}
            </div>
          )}
          {unreadable && (
            <div className="problem" role="alert">
              {t.fallback}
            </div>
          )}

          {proposal.diff_from_current.length > 0 && (
            <ul className="changes">
              {changes.map((ch, i) => (
                <li key={i} className="change">
                  <span className={`change-word ${ch.change}`}>{c.changeWord(ch)}</span>
                  <span>{c.changeText(ch)}</span>
                </li>
              ))}
            </ul>
          )}

          {questions.length > 0 && (
            <div className="questions">
              <h3 className="title">{t.before}</h3>
              {questions.map((q, i) =>
                skipped.has(i) ? (
                  <p key={i} className="note">
                    {t.skipped(q.question)}{' '}
                    <button type="button" className="link accent" onClick={() => setSkipped((s) => new Set([...s].filter((x) => x !== i)))}>
                      {t.undo}
                    </button>
                  </p>
                ) : (
                  <div key={i} className="field">
                    <label htmlFor={`q-${i}`}>{q.question}</label>
                    {q.why && <p className="field-help">{q.why}</p>}
                    <div className="field-row">
                      <input id={`q-${i}`} value={answers[i] ?? ''} onChange={(e) => setAnswers((a) => ({ ...a, [i]: e.target.value }))} />
                      <button type="button" className="btn plain" onClick={() => setSkipped((s) => new Set(s).add(i))}>
                        {t.skip}
                      </button>
                    </div>
                  </div>
                ),
              )}
              {typed && (
                <div>
                  <button type="button" className="btn plain accent-text" onClick={applyAnswers} disabled={busy !== null}>
                    {t.addAnswers}
                  </button>
                </div>
              )}
            </div>
          )}

          {proposal.assumptions.length > 0 && (
            <div className="more flush">
              <details>
                <summary>{t.assumed(proposal.assumptions.length)}</summary>
                <ul className="more-body">
                  {proposal.assumptions.map((a, i) => (
                    <li key={i}>
                      <p>{a}</p>
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          )}

          {confirming ? (
            <div className="confirm" role="alertdialog" aria-labelledby="confirm-title">
              <p className="title" id="confirm-title" ref={confirmTitle} tabIndex={-1}>
                {t.sure}
              </p>
              <ul>
                {looser.map((ch, i) => (
                  <li key={i}>{c.loosenSentence(ch)}</li>
                ))}
              </ul>
              <div className="actions">
                <button type="button" className="btn" onClick={save} disabled={busy !== null}>
                  {busy === 'save' ? t.saving : t.yesSave}
                </button>
                <button type="button" className="btn plain" onClick={() => setConfirming(false)}>
                  {t.goBack}
                </button>
              </div>
            </div>
          ) : (
            <div className="decide">
              <button type="button" className="btn" onClick={save} disabled={busy !== null || open.length > 0 || unreadable}>
                {busy === 'save' ? t.saving : t.save}
              </button>
              <button type="button" className="btn plain" onClick={() => setProposal(null)}>
                {t.discard}
              </button>
              {open.length > 0 && <p className="hint note">{t.answerFirst}</p>}
            </div>
          )}
        </section>
      )}

      {/* HOOK: weekly menus are maintained alongside the chef's ordering rules. */}
      <WeeklyMenus />
    </>
  )
}
