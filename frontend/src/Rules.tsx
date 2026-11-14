import { useEffect, useRef, useState, type FormEvent } from 'react'
import { compileRules, getKeys, getMandate, MOCK, saveMandate } from './api'
import { changeText, changeWord, loosenSentence, ruleLines, ruleWords } from './copy'
import { errorText } from './format'
import type { CompileResult, Mandate } from './types'

type Props = { refreshKey: number; onAction: () => void; onAnnounce: (text: string) => void }

// The chef's rules: read them in plain words, rewrite them in plain words, check what changes, then save.
// Compile never saves; saving needs every open question answered or skipped, and a second yes for anything looser.
export function Rules({ refreshKey, onAction, onAnnounce }: Props) {
  const approverKey = getKeys().approverKey
  const canRead = MOCK || Boolean(approverKey)
  const [current, setCurrent] = useState<Mandate | null | undefined>(undefined) // undefined = loading
  const [loadError, setLoadError] = useState<string | null>(null)
  const [text, setText] = useState<string | null>(null) // null until the current rules prefill it
  const [proposal, setProposal] = useState<CompileResult | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [skipped, setSkipped] = useState<Set<number>>(new Set())
  const [busy, setBusy] = useState<'check' | 'save' | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoadError(null)
    if (!canRead) return
    getMandate().then(
      (m) => {
        if (cancelled) return
        setCurrent(m)
        setText((t) => t ?? (m ? ruleWords(m) : ''))
      },
      (e) => !cancelled && setLoadError(errorText(e)),
    )
    return () => {
      cancelled = true
    }
  }, [canRead, approverKey, refreshKey])

  useEffect(() => {
    if (proposal || saved) heading.current?.focus()
  }, [proposal, saved])

  async function check(withText: string) {
    setBusy('check')
    setError(null)
    setSaved(null)
    setConfirming(false)
    onAnnounce('Reading your rules…')
    try {
      const res = await compileRules(withText)
      setProposal(res)
      setAnswers({})
      setSkipped(new Set())
      const n = res.diff_from_current.length
      onAnnounce(`${n} change${n === 1 ? '' : 's'} to your rules. Not saved yet.`)
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

  // Answers go back into the rules as plain sentences, and the rules are read again.
  function applyAnswers() {
    const added = Object.values(answers).map((a) => a.trim()).filter(Boolean)
    const next = [text ?? '', ...added].join('\n').trim()
    setText(next)
    void check(next)
  }

  const questions = proposal?.open_questions ?? []
  const open = questions.map((_, i) => i).filter((i) => !skipped.has(i))
  const typed = open.some((i) => answers[i]?.trim())
  const looser = proposal?.diff_from_current.filter((c) => c.change === 'looser') ?? []

  async function save() {
    if (!proposal || open.length) return
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
        proposal.diff_from_current.some((c) => c.needs_confirmation),
      )
      setCurrent(res.mandate)
      setText(ruleWords(res.mandate))
      setProposal(null)
      setConfirming(false)
      const n = res.changes.length
      setSaved(n ? `Saved. ${n} change${n === 1 ? '' : 's'} to your rules.` : 'Saved. Your rules are the same as before.')
      onAnnounce('Rules saved.')
      onAction()
    } catch (err) {
      setError(errorText(err))
      setConfirming(false)
    } finally {
      setBusy(null)
    }
  }

  if (!canRead) return <p className="problem">Add your approver key under Keys to see and change your rules.</p>

  return (
    <>
      <div className="ask">
        <h1 className="title">Your rules</h1>
        <p className="note">What the agent follows on every order. Valio’s front door checks them again.</p>
      </div>
      {loadError && (
        <div className="problem" role="alert">
          <strong>Couldn’t load your rules.</strong>
          {loadError}
        </div>
      )}
      {current === undefined && !loadError && <p className="note empty">Loading your rules…</p>}
      {current === null && <p className="note empty">No rules yet. Until you add some, the agent asks you about every order.</p>}
      {current && (
        <ul className="rules">
          {ruleLines(current).map((r, i) => (
            <li key={i}>
              <p>{r.text}</p>
              {r.said && <p className="quiet small">You said: “{r.said}”</p>}
            </li>
          ))}
        </ul>
      )}

      {text !== null && (
        <form className="ask section-gap" onSubmit={submit}>
          <label className="ask-label" htmlFor="rules-text">
            Tell the agent your rules
          </label>
          <p className="note">Write them the way you’d tell a new cook. Anything you leave out goes back to the safe default.</p>
          <textarea
            id="rules-text"
            className="ask-field rules-field"
            rows={6}
            maxLength={4000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Never anything with peanuts. Order on your own up to €1,500; above that, ask me."
            required
          />
          <div className="ask-row">
            <p className="note">Nothing changes until you save.</p>
            <button type="submit" className="btn" disabled={busy !== null || !text.trim()}>
              {busy === 'check' ? 'Reading…' : 'Check the changes'}
            </button>
          </div>
        </form>
      )}

      {busy === 'check' && (
        <div className="working">
          <p>Reading your rules and comparing them with the ones in force…</p>
          <div className="working-bar" aria-hidden="true" />
        </div>
      )}
      {error && (
        <div className="problem" role="alert">
          <strong>That didn’t go through.</strong>
          {error}
        </div>
      )}

      {saved && !proposal && (
        <section className="answer" aria-label="Saved">
          <p className="status good">Saved</p>
          <h2 ref={heading} tabIndex={-1} className="answer-text">
            {saved}
          </h2>
          <p className="answer-sub">The agent uses them from the next order. The change is in History.</p>
        </section>
      )}

      {proposal && (
        <section className="answer" aria-label="Proposed rules">
          <p className="status neutral">Not saved yet</p>
          <h2 ref={heading} tabIndex={-1} className="answer-text">
            {proposal.diff_from_current.length
              ? `${proposal.diff_from_current.length} change${proposal.diff_from_current.length === 1 ? '' : 's'} to your rules.`
              : 'No changes to your rules.'}
          </h2>
          {proposal.injection_flagged && (
            <div className="problem">
              <strong>Part of this reads like an instruction to the agent, not a rule.</strong>
              Check where the text came from before you save.
            </div>
          )}
          {proposal.used_fallback && (
            <p className="sure unsure">Gemini wasn’t available, so a simpler reader was used. Check the changes carefully.</p>
          )}

          {proposal.diff_from_current.length > 0 && (
            <ul className="changes">
              {proposal.diff_from_current.map((c, i) => (
                <li key={i} className="change">
                  <span className={`change-word ${c.change}`}>{changeWord(c)}</span>
                  <span>{changeText(c)}</span>
                </li>
              ))}
            </ul>
          )}

          {questions.length > 0 && (
            <div className="questions">
              <h3 className="title">Before you save</h3>
              {questions.map((q, i) =>
                skipped.has(i) ? (
                  <p key={i} className="note">
                    Skipped: {q.question}{' '}
                    <button type="button" className="link accent" onClick={() => setSkipped((s) => new Set([...s].filter((x) => x !== i)))}>
                      Undo
                    </button>
                  </p>
                ) : (
                  <div key={i} className="field">
                    <label htmlFor={`q-${i}`}>{q.question}</label>
                    {q.why && <p className="field-help">{q.why}</p>}
                    <div className="field-row">
                      <input id={`q-${i}`} value={answers[i] ?? ''} onChange={(e) => setAnswers((a) => ({ ...a, [i]: e.target.value }))} />
                      <button type="button" className="btn plain" onClick={() => setSkipped((s) => new Set(s).add(i))}>
                        Skip
                      </button>
                    </div>
                  </div>
                ),
              )}
              {typed && (
                <div>
                  <button type="button" className="btn plain accent-text" onClick={applyAnswers} disabled={busy !== null}>
                    Add my answers and check again
                  </button>
                </div>
              )}
            </div>
          )}

          {proposal.assumptions.length > 0 && (
            <div className="more flush">
              <details>
                <summary>What the agent assumed ({proposal.assumptions.length})</summary>
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
              <p className="title" id="confirm-title">
                Are you sure?
              </p>
              <ul>
                {looser.map((c, i) => (
                  <li key={i}>{loosenSentence(c)}</li>
                ))}
              </ul>
              <div className="actions">
                <button type="button" className="btn" onClick={save} disabled={busy !== null}>
                  {busy === 'save' ? 'Saving…' : 'Yes, save these rules'}
                </button>
                <button type="button" className="btn plain" onClick={() => setConfirming(false)}>
                  Go back
                </button>
              </div>
            </div>
          ) : (
            <div className="decide">
              <button type="button" className="btn" onClick={save} disabled={busy !== null || open.length > 0}>
                {busy === 'save' ? 'Saving…' : 'Save rules'}
              </button>
              <button type="button" className="btn plain" onClick={() => setProposal(null)}>
                Discard
              </button>
              {open.length > 0 && <p className="hint note">Answer or skip the questions above first.</p>}
            </div>
          )}
        </section>
      )}
    </>
  )
}
