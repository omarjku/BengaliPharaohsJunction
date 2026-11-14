import { useEffect, useState } from 'react'
import { getKeys, getProfile, MOCK } from './api'
import {
  clearExampleHistory,
  deleteStandingOrder,
  getKitchenHistory,
  saveKitchenCovers,
  saveStandingOrder,
  type KitchenHistory,
  type StandingOrderLine,
  type Weekday,
  WEEKDAYS,
} from './kitchenEditApi'
import { KITCHEN_EDIT_COPY } from './kitchenEditCopy'
import { useCopy } from './i18n'
import { errorText } from './format'
import './HistoryEditor.css'

type CoverValues = Record<Weekday, string>
type LinesByDay = Record<Weekday, StandingOrderLine[]>

const blankLine = (): StandingOrderLine => ({ text: '' })

function coverValues(history: KitchenHistory): CoverValues {
  return Object.fromEntries(WEEKDAYS.map((day) => [day, history.covers_by_weekday[day] === null ? '' : String(history.covers_by_weekday[day])])) as CoverValues
}

function lineValues(history: KitchenHistory): LinesByDay {
  return Object.fromEntries(WEEKDAYS.map((day) => [day, structuredClone(history.standing_orders.find((order) => order.weekday === day)?.lines ?? [])])) as LinesByDay
}

export function HistoryEditor({ refreshKey = 0 }: { refreshKey?: number }) {
  const c = useCopy()
  const t = KITCHEN_EDIT_COPY[c.LANG].history
  const { agentKey, approverKey } = getKeys()
  const hasAgent = MOCK || !!agentKey
  const hasApprover = MOCK || !!approverKey
  const [history, setHistory] = useState<KitchenHistory | null>(null)
  const [demoKitchen, setDemoKitchen] = useState(false)
  const [loading, setLoading] = useState(hasAgent)
  const [error, setError] = useState<string | null>(null)
  const [covers, setCovers] = useState<CoverValues>({ mon: '', tue: '', wed: '', thu: '', fri: '', sat: '', sun: '' })
  const [lines, setLines] = useState<LinesByDay>({ mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: [] })
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  function load() {
    if (!hasAgent) {
      setLoading(false)
      setHistory(null)
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([getKitchenHistory(), getProfile().catch(() => null)]).then(
      ([next, profile]) => {
        setHistory(next)
        setCovers(coverValues(next))
        setLines(lineValues(next))
        setDemoKitchen(profile?.buyer_id.startsWith('try-') ?? false)
        setLoading(false)
      },
      (err) => {
        setError(errorText(err))
        setLoading(false)
      },
    )
  }

  useEffect(load, [agentKey, hasAgent, refreshKey])

  function coverNumber(value: string): number | null {
    if (!/^\d+$/.test(value.trim())) return null
    const number = Number(value)
    return Number.isSafeInteger(number) && number >= 0 ? number : null
  }

  const coversReady = WEEKDAYS.every((day) => coverNumber(covers[day]) !== null)

  async function saveCovers() {
    if (!coversReady || !hasApprover) return
    setBusy('covers')
    setNotice(null)
    setError(null)
    try {
      const values = Object.fromEntries(WEEKDAYS.map((day) => [day, coverNumber(covers[day])])) as Record<Weekday, number>
      await saveKitchenCovers(values)
      setNotice(t.coversSaved)
      load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  async function replaceExample() {
    if (!hasApprover) return
    setBusy('example')
    setNotice(null)
    setError(null)
    try {
      await clearExampleHistory()
      setNotice(t.replaced)
      load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  function updateLine(day: Weekday, index: number, field: keyof StandingOrderLine, value: string) {
    setLines((current) => ({
      ...current,
      [day]: current[day].map((line, lineIndex) => {
        if (lineIndex !== index) return line
        if (field === 'text' || field === 'unit') return { ...line, [field]: value }
        const quantity = value.trim() === '' ? undefined : Number(value)
        return { ...line, quantity: quantity !== undefined && Number.isFinite(quantity) ? quantity : undefined }
      }),
    }))
  }

  function addLine(day: Weekday) {
    setLines((current) => ({ ...current, [day]: [...current[day], blankLine()] }))
  }

  function removeLine(day: Weekday, index: number) {
    setLines((current) => ({ ...current, [day]: current[day].filter((_, lineIndex) => lineIndex !== index) }))
  }

  async function saveDay(day: Weekday) {
    if (!hasApprover) return
    setBusy(`save-${day}`)
    setNotice(null)
    setError(null)
    try {
      const nextLines = lines[day].filter((line) => line.text.trim()).map((line) => ({
        ...line,
        text: line.text.trim(),
        unit: line.unit?.trim() || undefined,
      }))
      await saveStandingOrder(day, nextLines)
      setNotice(t.saved)
      load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  async function deleteDay(day: Weekday) {
    if (!hasApprover) return
    setBusy(`delete-${day}`)
    setNotice(null)
    setError(null)
    try {
      await deleteStandingOrder(day)
      setNotice(t.saved)
      load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  if (!hasAgent) {
    return (
      <section className="kitchen-edit-section">
        <h2 className="title">{t.title}</h2>
        <p className="note">{t.intro}</p>
        <p className="interview-note" role="status">{t.noAgent}</p>
      </section>
    )
  }

  if (loading) return <section className="kitchen-edit-section"><h2 className="title">{t.title}</h2><p className="quiet">{t.loading}</p></section>
  if (error && !history) return <section className="kitchen-edit-section"><h2 className="title">{t.title}</h2><p className="interview-error" role="alert">{error || t.failed}</p></section>
  if (!history) return null

  const showExample = history.basis !== 'own'
  return (
    <section className="kitchen-edit-section" aria-labelledby="history-editor-title">
      <div className="kitchen-edit-heading">
        <div>
          <h2 id="history-editor-title" className="title">{t.title}</h2>
          <p className="note">{t.intro}</p>
        </div>
        <span className="kitchen-history-tag">{history.labels.example || t.exampleTag}</span>
      </div>

      {showExample && (
        <div className="kitchen-history-banner" role="status">
          <p>{demoKitchen ? t.bannerTry : t.bannerExample}</p>
          <button type="button" className="btn plain" onClick={replaceExample} disabled={busy !== null || !hasApprover}>
            {busy === 'example' ? t.replacing : t.replace}
          </button>
        </div>
      )}

      {!hasApprover && <p className="interview-note" role="status">{t.noApprover}</p>}

      <div className="kitchen-edit-block">
        <h3 className="title">{t.coversTitle}</h3>
        <div className="kitchen-covers-grid">
          {WEEKDAYS.map((day) => (
            <label className="kitchen-cover" key={day}>
              <span>{KITCHEN_EDIT_COPY[c.LANG].weekdays[day]}</span>
              <span className="kitchen-stepper">
                <button type="button" aria-label={`${t.coversTitle} − ${KITCHEN_EDIT_COPY[c.LANG].weekdays[day]}`} onClick={() => setCovers((current) => ({ ...current, [day]: String(Math.max(0, (coverNumber(current[day]) ?? 0) - 1)) }))} disabled={!hasApprover || busy !== null}>−</button>
                <input inputMode="numeric" type="number" min="0" step="1" value={covers[day]} onChange={(event) => setCovers((current) => ({ ...current, [day]: event.target.value }))} aria-label={KITCHEN_EDIT_COPY[c.LANG].weekdays[day]} disabled={!hasApprover || busy !== null} />
                <button type="button" aria-label={`${t.coversTitle} + ${KITCHEN_EDIT_COPY[c.LANG].weekdays[day]}`} onClick={() => setCovers((current) => ({ ...current, [day]: String((coverNumber(current[day]) ?? 0) + 1) }))} disabled={!hasApprover || busy !== null}>+</button>
              </span>
              <small className={history.covers_source[day] === 'example' ? 'quiet' : 'faint'}>{history.covers_source[day] === 'example' ? t.example : t.own}</small>
            </label>
          ))}
        </div>
        {!coversReady && <p className="quiet small">{t.invalidCovers}</p>}
        <button type="button" className="btn" onClick={saveCovers} disabled={!hasApprover || busy !== null || !coversReady}>{busy === 'covers' ? t.saving : t.saveCovers}</button>
      </div>

      <div className="kitchen-edit-block">
        <h3 className="title">{t.standingTitle}</h3>
        <div className="kitchen-orders">
          {WEEKDAYS.map((day) => {
            const dayLines = lines[day]
            const existing = history.standing_orders.find((order) => order.weekday === day)
            return (
              <fieldset className="kitchen-order" key={day}>
                <legend>{KITCHEN_EDIT_COPY[c.LANG].weekdays[day]} {existing && <small className={existing.source === 'example' ? 'quiet' : 'faint'}>{existing.source === 'example' ? t.example : t.own}</small>}</legend>
                {dayLines.length ? dayLines.map((line, index) => (
                  <div className="kitchen-line" key={`${day}-${index}`}>
                    <label className="field kitchen-line-text"><span>{t.lineText}</span><input value={line.text} placeholder={t.linePlaceholder} onChange={(event) => updateLine(day, index, 'text', event.target.value)} disabled={!hasApprover || busy !== null} /></label>
                    <label className="field"><span>{t.quantity}</span><input inputMode="decimal" type="number" min="0" step="any" value={line.quantity ?? ''} onChange={(event) => updateLine(day, index, 'quantity', event.target.value)} disabled={!hasApprover || busy !== null} /></label>
                    <label className="field"><span>{t.unit}</span><input value={line.unit ?? ''} onChange={(event) => updateLine(day, index, 'unit', event.target.value)} disabled={!hasApprover || busy !== null} /></label>
                    <button type="button" className="btn plain bad kitchen-remove" onClick={() => removeLine(day, index)} disabled={!hasApprover || busy !== null}>{t.removeLine}</button>
                  </div>
                )) : <p className="quiet small">{t.empty}</p>}
                <div className="actions kitchen-order-actions">
                  <button type="button" className="btn plain" onClick={() => addLine(day)} disabled={!hasApprover || busy !== null}>{t.addLine}</button>
                  <button type="button" className="btn" onClick={() => saveDay(day)} disabled={!hasApprover || busy !== null}>{busy === `save-${day}` ? t.savingLine : t.save}</button>
                  {existing && <button type="button" className="btn plain bad" onClick={() => deleteDay(day)} disabled={!hasApprover || busy !== null}>{busy === `delete-${day}` ? t.deleting : t.delete}</button>}
                </div>
              </fieldset>
            )
          })}
        </div>
      </div>

      {notice && <p className="interview-success" role="status">{notice}</p>}
      {error && <p className="interview-error" role="alert">{error}</p>}
    </section>
  )
}
