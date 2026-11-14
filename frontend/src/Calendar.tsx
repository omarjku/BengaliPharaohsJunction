import { useEffect, useMemo, useRef, useState } from 'react'
import { errorText } from './format'
import { getCalendarCopy } from './calendarCopy'
import { calendarWeekdays } from './calendarCopy'
import {
  getCalendar,
  getWeeklyMenus,
  planWeeklyMenu,
  type CalendarDay,
  type CalendarEntry,
  type Weekday,
  type WeeklyMenu,
} from './calendarApi'
import type { MenuRun } from './types'
import { useCopy } from './i18n'
import { CalendarIcon } from './CalendarIcon'
import { DayList } from './DayList'
import { MenuDetail } from './MenuDetail'
import './Calendar.css'

type Props = {
  onPrefill: (text: string) => void
  onMenuPlanned: (plan: MenuRun, date: string, covers: number) => void
}

function todayYmd(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki' }).format(new Date())
}

function dateFromYmd(date: string): Date {
  return new Date(`${date}T12:00:00Z`)
}

function ymd(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function monthStart(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1, 12))
}

function monthKey(date: Date): string {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
}

function addMonths(date: Date, amount: number): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + amount, 1, 12))
}

function addDays(date: string, amount: number): string {
  const next = dateFromYmd(date)
  next.setUTCDate(next.getUTCDate() + amount)
  return ymd(next)
}

function visibleDates(month: Date): string[] {
  const first = monthStart(month)
  const leading = (first.getUTCDay() + 6) % 7
  const daysInMonth = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0, 12)).getUTCDate()
  const total = Math.ceil((leading + daysInMonth) / 7) * 7
  return Array.from({ length: total }, (_, index) => {
    const date = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1 - leading + index, 12))
    return ymd(date)
  })
}

function rangeFor(month: Date): { from: string; to: string } {
  const dates = visibleDates(month)
  return { from: dates[0], to: dates[dates.length - 1] }
}

function weekdayFor(date: string): Weekday {
  const index = (dateFromYmd(date).getUTCDay() + 6) % 7
  return calendarWeekdays[index]
}

function daySummary(day: CalendarDay | undefined, copy: ReturnType<typeof getCalendarCopy>): string {
  if (!day) return ''
  const deliveries = day.entries.filter((entry) => entry.kind === 'delivery_confirmed').length
  const pending = day.entries.filter((entry) => entry.kind === 'delivery_pending').length
  const recurring = day.entries.filter((entry) => entry.kind === 'recurring_order').length
  const menu = day.entries.find((entry): entry is Extract<CalendarEntry, { kind: 'weekly_menu' }> => entry.kind === 'weekly_menu')
  return copy.daySummary(deliveries, pending, recurring, menu?.name ?? null)
}

function markKinds(day: CalendarDay | undefined): string[] {
  if (!day) return []
  const kinds: string[] = []
  const has = (kind: CalendarEntry['kind']) => day.entries.some((entry) => entry.kind === kind)
  if (has('delivery_confirmed')) kinds.push('delivery')
  if (has('delivery_pending')) kinds.push('pending')
  if (has('recurring_order')) kinds.push('recurring')
  if (has('weekly_menu')) kinds.push('menu')
  return kinds.slice(0, 3)
}

export function Calendar({ onPrefill, onMenuPlanned }: Props) {
  const { LANG } = useCopy()
  const copy = getCalendarCopy(LANG)
  const today = todayYmd()
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState(() => monthStart(dateFromYmd(today)))
  const [selected, setSelected] = useState(today)
  const [calendar, setCalendar] = useState<CalendarDay[]>([])
  const [menus, setMenus] = useState<WeeklyMenu[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [menuDetail, setMenuDetail] = useState<WeeklyMenu | null>(null)
  const [planning, setPlanning] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const sheetRef = useRef<HTMLElement>(null)
  const iconRef = useRef<HTMLButtonElement>(null)
  const dayButtonRefs = useRef(new Map<string, HTMLButtonElement>())
  const gesture = useRef<{ x: number; y: number } | null>(null)
  const range = useMemo(() => rangeFor(month), [month])
  const dates = useMemo(() => visibleDates(month), [month])
  const days = useMemo(() => new Map(calendar.map((day) => [day.date, day])), [calendar])
  const todayDay = days.get(today)
  const selectedDay = days.get(selected) ?? null
  const selectedMenu = menuDetail ?? menus.find((menu) => menu.active && menu.weekday === weekdayFor(selected)) ?? null

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([getCalendar(range.from, range.to), getWeeklyMenus()]).then(
      ([calendarResult, menuResult]) => {
        if (cancelled) return
        setCalendar(calendarResult.days)
        setMenus(menuResult)
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
  }, [range.from, range.to, refresh])

  useEffect(() => {
    if (!open) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('keydown', closeOnEscape)
    requestAnimationFrame(() => sheetRef.current?.querySelector<HTMLButtonElement>('.calendar-close')?.focus())
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [open])

  function close() {
    setOpen(false)
    setMenuDetail(null)
    requestAnimationFrame(() => iconRef.current?.focus())
  }

  function changeMonth(amount: number) {
    setMonth((current) => addMonths(current, amount))
    setMenuDetail(null)
  }

  function selectDay(date: string) {
    setSelected(date)
    if (monthKey(dateFromYmd(date)) !== monthKey(month)) setMonth(monthStart(dateFromYmd(date)))
    setMenuDetail(null)
  }

  function moveDay(date: string, amount: number) {
    const next = addDays(date, amount)
    selectDay(next)
    requestAnimationFrame(() => dayButtonRefs.current.get(next)?.focus())
  }

  function refreshCalendar() {
    setRefresh((value) => value + 1)
  }

  function prefill(text: string) {
    close()
    onPrefill(text)
  }

  async function planMenu() {
    if (!menuDetail) return
    setPlanning(true)
    setError(null)
    try {
      const plan = await planWeeklyMenu(menuDetail.weekday, selected)
      const covers = menuDetail.covers ?? 0
      close()
      onMenuPlanned(plan, selected, covers)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setPlanning(false)
    }
  }

  const hasTodayItems = Boolean(todayDay?.entries.length)

  return (
    <div className="calendar-root">
      <div className="calendar-launch">
        <CalendarIcon
          date={today}
          label={copy.iconLabel(copy.dateTitle(today), hasTodayItems)}
          open={open}
          hasItems={hasTodayItems}
          onClick={() => setOpen(true)}
          buttonRef={iconRef}
        />
      </div>

      {open && (
        <div
          className="calendar-overlay"
          onPointerDown={(event) => {
            if (event.target === event.currentTarget) close()
          }}
        >
          <section
            ref={sheetRef}
            id="calendar-sheet"
            className="calendar-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="calendar-title"
            onPointerDown={(event) => {
              if (event.pointerType === 'touch') gesture.current = { x: event.clientX, y: event.clientY }
            }}
            onPointerUp={(event) => {
              const start = gesture.current
              gesture.current = null
              if (!start || event.pointerType !== 'touch') return
              const dx = event.clientX - start.x
              const dy = event.clientY - start.y
              if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 48) changeMonth(dx < 0 ? 1 : -1)
              if (dy > 72 && Math.abs(dy) > Math.abs(dx)) close()
            }}
          >
            <div className="calendar-sheet-head">
              <div>
                <p className="calendar-section-label">{copy.calendar}</p>
                <h1 id="calendar-title" className="calendar-title">
                  {copy.monthTitle(month)}
                </h1>
              </div>
              <button type="button" className="calendar-close" aria-label={copy.close} onClick={close}>
                <span aria-hidden="true">×</span>
              </button>
            </div>

            <div className="calendar-month-toolbar">
              <button type="button" className="calendar-month-nav" aria-label={copy.previousMonth} onClick={() => changeMonth(-1)}>
                <span className="calendar-chevron previous" aria-hidden="true" />
              </button>
              <p className="calendar-month-label">{copy.month}</p>
              <button type="button" className="calendar-month-nav" aria-label={copy.nextMonth} onClick={() => changeMonth(1)}>
                <span className="calendar-chevron next" aria-hidden="true" />
              </button>
            </div>

            <div className="calendar-grid" aria-label={copy.monthTitle(month)}>
              <div className="calendar-weekdays" aria-hidden="true">
                {calendarWeekdays.map((weekday) => (
                  <span key={weekday}>{copy.weekdayShort[weekday]}</span>
                ))}
              </div>
              <div className="calendar-days">
                {dates.map((date) => {
                  const day = days.get(date)
                  const inMonth = date.slice(0, 7) === monthKey(month)
                  const marks = markKinds(day)
                  const isToday = date === today
                  const isSelected = date === selected
                  return (
                    <button
                      key={date}
                      type="button"
                      ref={(element) => {
                        if (element) dayButtonRefs.current.set(date, element)
                        else dayButtonRefs.current.delete(date)
                      }}
                      className={`calendar-day${inMonth ? '' : ' outside'}${isToday ? ' today' : ''}${isSelected ? ' selected' : ''}`}
                      aria-label={copy.dayAria(date, daySummary(day, copy))}
                      aria-current={isToday ? 'date' : undefined}
                      aria-pressed={isSelected}
                      onClick={() => selectDay(date)}
                      onKeyDown={(event) => {
                        if (event.key === 'ArrowLeft') {
                          event.preventDefault()
                          moveDay(date, -1)
                        } else if (event.key === 'ArrowRight') {
                          event.preventDefault()
                          moveDay(date, 1)
                        } else if (event.key === 'ArrowUp') {
                          event.preventDefault()
                          moveDay(date, -7)
                        } else if (event.key === 'ArrowDown') {
                          event.preventDefault()
                          moveDay(date, 7)
                        } else if (event.key === 'Enter') {
                          event.preventDefault()
                          selectDay(date)
                        }
                      }}
                    >
                      <span className="calendar-day-number">{Number(date.slice(-2))}</span>
                      <span className="calendar-marks" aria-hidden="true">
                        {marks.map((kind) => <span key={kind} className={`calendar-mark ${kind}`} />)}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>

            {loading && <p className="note calendar-loading" role="status">{copy.loading}</p>}
            {error && (
              <div className="calendar-error" role="alert">
                <strong>{copy.loadFailed}</strong> {error}
              </div>
            )}

            {selectedMenu && menuDetail ? (
              <MenuDetail menu={selectedMenu} date={selected} copy={copy} busy={planning} onBack={() => setMenuDetail(null)} onPlan={() => void planMenu()} />
            ) : (
              <DayList
                date={selected}
                day={selectedDay}
                menu={selectedMenu}
                copy={copy}
                onOpenMenu={setMenuDetail}
                onPrefill={prefill}
                onChanged={refreshCalendar}
              />
            )}
          </section>
        </div>
      )}
    </div>
  )
}
