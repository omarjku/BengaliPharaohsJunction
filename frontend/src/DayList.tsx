import { useState } from 'react'
import { decideOrder } from './api'
import { errorText, formatCents } from './format'
import type { CalendarCopy } from './calendarCopy'
import { placeRecurring, skipRecurring, type CalendarDay, type Weekday, type WeeklyMenu } from './calendarApi'

type Props = {
  date: string
  day: CalendarDay | null
  menu: WeeklyMenu | null
  copy: CalendarCopy
  onOpenMenu: (menu: WeeklyMenu) => void
  onPrefill: (text: string) => void
  onChanged: () => void
}

function statusClass(kind: 'confirmed' | 'pending'): string {
  return kind === 'pending' ? 'calendar-status warn' : 'calendar-status good'
}

function cutoffTime(closingTime: string): string {
  return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Helsinki' }).format(new Date(closingTime))
}

function linesFor(entry: { lines: { name: string; quantity: number; unit: string | null }[] }, copy: CalendarCopy) {
  return (
    <ul className="calendar-lines">
      {entry.lines.map((line, index) => (
        <li key={`${line.name}-${index}`}>{copy.line(line)}</li>
      ))}
    </ul>
  )
}

export function DayList({ date, day, menu, copy, onOpenMenu, onPrefill, onChanged }: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const entries = day?.entries ?? []

  async function approve(orderId: string) {
    setBusy(`approve:${orderId}`)
    setError(null)
    try {
      await decideOrder(orderId, 'approve')
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  async function changeRecurring(weekday: Weekday, action: 'place' | 'skip') {
    const key = `${action}:${weekday}`
    setBusy(key)
    setError(null)
    try {
      if (action === 'place') await placeRecurring(weekday, date)
      else await skipRecurring(weekday, date)
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="calendar-day-list" aria-labelledby="calendar-day-title">
      <div className="calendar-day-heading">
        <div>
          <p className="calendar-section-label">{copy.dayList}</p>
          <h2 id="calendar-day-title" className="calendar-day-title">
            {copy.dateTitle(date)}
          </h2>
        </div>
        {day?.cutoff && <p className={`calendar-cutoff${day.cutoff.passed ? ' passed' : ''}`}>{copy.cutoff(cutoffTime(day.cutoff.closing_time), day.cutoff.passed)}</p>}
      </div>

      {error && (
        <div className="calendar-error" role="alert">
          {error}
        </div>
      )}

      {entries.length === 0 ? (
        <div className="calendar-empty">
          <p className="calendar-empty-title">{copy.emptyTitle}</p>
          <p className="note">{copy.emptyBody}</p>
          <button type="button" className="btn plain calendar-empty-action" onClick={() => onPrefill(copy.askForDay(copy.dateTitle(date)))}>
            {copy.askForDay(copy.dateTitle(date))}
          </button>
        </div>
      ) : (
        <div className="calendar-entry-list">
          {entries.map((entry, index) => {
            if (entry.kind === 'delivery_confirmed' || entry.kind === 'delivery_pending') {
              const pending = entry.kind === 'delivery_pending'
              return (
                <article key={`${entry.kind}-${entry.order_id}-${index}`} className="calendar-entry calendar-delivery">
                  <div className="calendar-entry-heading">
                    <div>
                      <p className={statusClass(pending ? 'pending' : 'confirmed')}>
                        {pending ? copy.pending : copy.confirmed}
                      </p>
                      <h3>{entry.title}</h3>
                    </div>
                    <strong className="calendar-total num">{copy.total(formatCents(entry.total_cents))}</strong>
                  </div>
                  {linesFor(entry, copy)}
                  {pending && (
                    <>
                      <p className="calendar-entry-note">{entry.reason}</p>
                      <button
                        type="button"
                        className="btn calendar-entry-action"
                        disabled={busy !== null}
                        onClick={() => void approve(entry.order_id)}
                      >
                        {busy === `approve:${entry.order_id}` ? copy.approving : copy.approve}
                      </button>
                    </>
                  )}
                </article>
              )
            }

            if (entry.kind === 'recurring_order') {
              return (
                <article key={`recurring-${entry.weekday}-${index}`} className="calendar-entry calendar-recurring">
                  <div className="calendar-entry-heading">
                    <div>
                      <p className="calendar-status recurring">{copy.recurring}</p>
                      <h3>{copy.recurringSource}</h3>
                    </div>
                    <span className="calendar-entry-state">{entry.placed ? copy.placed : copy.notPlaced}</span>
                  </div>
                  {linesFor(entry, copy)}
                  <p className="calendar-entry-note">{entry.source}</p>
                  {entry.placed ? (
                    <p className="calendar-entry-note calendar-entry-done">{copy.placed}</p>
                  ) : (
                    <div className="calendar-entry-actions">
                      <button
                        type="button"
                        className="btn"
                        disabled={busy !== null}
                        onClick={() => void changeRecurring(entry.weekday, 'place')}
                      >
                        {busy === `place:${entry.weekday}` ? copy.placing : copy.place}
                      </button>
                      <button
                        type="button"
                        className="btn plain"
                        disabled={busy !== null}
                        onClick={() => void changeRecurring(entry.weekday, 'skip')}
                      >
                        {busy === `skip:${entry.weekday}` ? copy.skipping : copy.skip}
                      </button>
                    </div>
                  )}
                </article>
              )
            }

            if (entry.kind === 'weekly_menu') {
              return menu ? (
                <button key={`menu-${entry.name}-${index}`} type="button" className="calendar-entry calendar-menu-card" onClick={() => onOpenMenu(menu)}>
                  <span className="calendar-menu-icon" aria-hidden="true">·</span>
                  <span className="calendar-menu-copy">
                    <span className="calendar-status menu">{copy.weeklyMenu}</span>
                    <strong>{entry.name}</strong>
                    <span className="calendar-menu-meta">
                      {entry.dishes.length} {entry.dishes.length === 1 ? copy.dish : copy.dishes.toLowerCase()}
                      {entry.covers ? ` · ${copy.covers(entry.covers)}` : ''}
                    </span>
                  </span>
                  <span className="calendar-menu-open">{copy.viewMenu}</span>
                </button>
              ) : (
                <article key={`menu-${entry.name}-${index}`} className="calendar-entry calendar-menu-card calendar-menu-card-static">
                  <span className="calendar-menu-icon" aria-hidden="true">·</span>
                  <span className="calendar-menu-copy">
                    <span className="calendar-status menu">{copy.weeklyMenu}</span>
                    <strong>{entry.name}</strong>
                  </span>
                </article>
              )
            }

            return (
              <article key={`guests-${index}`} className="calendar-entry calendar-guests">
                <span className="calendar-menu-icon" aria-hidden="true">·</span>
                <div>
                  <p>{copy.guests(entry.value)}</p>
                  {entry.simulated && <p className="calendar-entry-note">{copy.simulated}</p>}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
