import { useEffect, useMemo, useState } from 'react'
import { getKeys, MOCK } from './api'
import { errorText } from './format'
import { calendarWeekdays, getCalendarCopy } from './calendarCopy'
import { deleteWeeklyMenu, getWeeklyMenus, saveWeeklyMenu, type Weekday, type WeeklyMenu, type WeeklyMenuDish } from './calendarApi'
import { useCopy } from './i18n'

function emptyMenu(weekday: Weekday): WeeklyMenu {
  return { weekday, name: '', dishes: [{ name: '', recipe: '' }], covers: undefined, active: true }
}

function asRecord(items: WeeklyMenu[]): Record<Weekday, WeeklyMenu> {
  const record = {} as Record<Weekday, WeeklyMenu>
  for (const weekday of calendarWeekdays) record[weekday] = emptyMenu(weekday)
  for (const menu of items) record[menu.weekday] = structuredClone(menu)
  return record
}

export function WeeklyMenus() {
  const { LANG } = useCopy()
  const copy = getCalendarCopy(LANG)
  const canEdit = MOCK || Boolean(getKeys().approverKey)
  const [menus, setMenus] = useState<Record<Weekday, WeeklyMenu>>(() => asRecord([]))
  const [saved, setSaved] = useState<Set<Weekday>>(new Set())
  const [weekday, setWeekday] = useState<Weekday>('fri')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<'save' | 'delete' | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const draft = menus[weekday]

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getWeeklyMenus().then(
      (items) => {
        if (cancelled) return
        setMenus(asRecord(items))
        setSaved(new Set(items.map((item) => item.weekday)))
        setLoading(false)
      },
      (err) => {
        if (cancelled) return
        setError(errorText(err))
        setLoading(false)
      },
    )
    return () => {
      cancelled = true
    }
  }, [LANG])

  const menuExists = saved.has(weekday)
  const dishCount = useMemo(() => draft.dishes.filter((dish) => dish.name.trim()).length, [draft.dishes])

  function updateDraft(change: Partial<WeeklyMenu>) {
    setMenus((current) => ({ ...current, [weekday]: { ...current[weekday], ...change } }))
  }

  function updateDish(index: number, change: Partial<WeeklyMenuDish>) {
    updateDraft({ dishes: draft.dishes.map((dish, i) => (i === index ? { ...dish, ...change } : dish)) })
  }

  function addDish() {
    updateDraft({ dishes: [...draft.dishes, { name: '', recipe: '' }] })
  }

  function removeDish(index: number) {
    const next = draft.dishes.filter((_, i) => i !== index)
    updateDraft({ dishes: next.length ? next : [{ name: '', recipe: '' }] })
  }

  async function save() {
    if (!draft.name.trim()) {
      setError(copy.needsName)
      return
    }
    if (!dishCount) {
      setError(copy.needsDish)
      return
    }
    setBusy('save')
    setError(null)
    setMessage(null)
    try {
      const next = {
        ...draft,
        weekday,
        name: draft.name.trim(),
        dishes: draft.dishes.filter((dish) => dish.name.trim()).map((dish) => ({ name: dish.name.trim(), recipe: dish.recipe?.trim() || undefined })),
        covers: draft.covers && draft.covers > 0 ? Math.round(draft.covers) : undefined,
        active: true,
      }
      const result = await saveWeeklyMenu(weekday, next)
      setMenus((current) => ({ ...current, [weekday]: result }))
      setSaved((current) => new Set(current).add(weekday))
      setMessage(copy.menuSaved)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    setBusy('delete')
    setError(null)
    setMessage(null)
    try {
      await deleteWeeklyMenu(weekday)
      setMenus((current) => ({ ...current, [weekday]: emptyMenu(weekday) }))
      setSaved((current) => new Set([...current].filter((item) => item !== weekday)))
      setMessage(copy.menuDeleted)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="weekly-menus section-gap" aria-labelledby="weekly-menus-title">
      <div className="weekly-menus-heading">
        <h2 id="weekly-menus-title" className="title">
          {copy.weeklyMenusTitle}
        </h2>
        <p className="note">{copy.weeklyMenusIntro}</p>
      </div>

      {!canEdit && <p className="problem">{copy.needApprover}</p>}
      {loading && <p className="note empty">{copy.loading}</p>}
      {error && (
        <div className="problem" role="alert">
          <strong>{copy.loadFailed}</strong>
          {error}
        </div>
      )}
      {message && <p className="note weekly-menu-message" role="status">{message}</p>}

      {!loading && (
        <>
          <div className="weekly-day-tabs" role="tablist" aria-label={copy.weeklyMenusTitle}>
            {calendarWeekdays.map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={weekday === item}
                className="weekly-day-tab"
                onClick={() => {
                  setWeekday(item)
                  setError(null)
                  setMessage(null)
                }}
              >
                {copy.weekdayShort[item]}
                {saved.has(item) && <span className="weekly-day-dot" aria-hidden="true" />}
              </button>
            ))}
          </div>

          <div className="weekly-menu-form">
            <p className="calendar-section-label">{copy.editMenuFor}</p>
            <h3 className="weekly-menu-weekday">{copy.weekdayLong[weekday]}</h3>
            {!menuExists && <p className="note">{copy.noMenu}</p>}
            <div className="field">
              <label htmlFor="weekly-menu-name">{copy.menuName}</label>
              <input
                id="weekly-menu-name"
                value={draft.name}
                placeholder={copy.menuNamePlaceholder}
                disabled={!canEdit || busy !== null}
                onChange={(event) => updateDraft({ name: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="weekly-menu-covers">{copy.usualCovers}</label>
              <input
                id="weekly-menu-covers"
                type="number"
                min="0"
                inputMode="numeric"
                value={draft.covers ?? ''}
                disabled={!canEdit || busy !== null}
                onChange={(event) => updateDraft({ covers: event.target.value ? Number(event.target.value) : undefined })}
              />
            </div>

            <div className="weekly-dishes">
              {draft.dishes.map((dish, index) => (
                <fieldset key={index} className="weekly-dish">
                  <legend>{copy.dishes} {index + 1}</legend>
                  <div className="field">
                    <label htmlFor={`weekly-dish-${index}`}>{copy.dishName}</label>
                    <input
                      id={`weekly-dish-${index}`}
                      value={dish.name}
                      placeholder={copy.dishNamePlaceholder}
                      disabled={!canEdit || busy !== null}
                      onChange={(event) => updateDish(index, { name: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`weekly-recipe-${index}`}>{copy.recipeLabel}</label>
                    <textarea
                      id={`weekly-recipe-${index}`}
                      rows={4}
                      maxLength={4000}
                      value={dish.recipe ?? ''}
                      placeholder={copy.recipePlaceholder}
                      disabled={!canEdit || busy !== null}
                      onChange={(event) => updateDish(index, { recipe: event.target.value })}
                    />
                  </div>
                  {draft.dishes.length > 1 && (
                    <button type="button" className="btn plain bad" disabled={!canEdit || busy !== null} onClick={() => removeDish(index)}>
                      {copy.removeDish}
                    </button>
                  )}
                </fieldset>
              ))}
              <button type="button" className="btn plain weekly-add-dish" disabled={!canEdit || busy !== null} onClick={addDish}>
                {copy.addDish}
              </button>
            </div>

            <div className="actions weekly-menu-actions">
              <button type="button" className="btn" disabled={!canEdit || busy !== null} onClick={() => void save()}>
                {busy === 'save' ? copy.savingMenu : copy.saveMenu}
              </button>
              {menuExists && (
                <button type="button" className="btn plain bad" disabled={!canEdit || busy !== null} onClick={() => void remove()}>
                  {busy === 'delete' ? copy.deletingMenu : copy.deleteMenu}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
