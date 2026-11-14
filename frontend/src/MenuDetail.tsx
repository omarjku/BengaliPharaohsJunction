import type { CalendarCopy } from './calendarCopy'
import type { WeeklyMenu } from './calendarApi'

type Props = {
  menu: WeeklyMenu
  date: string
  copy: CalendarCopy
  busy: boolean
  onBack: () => void
  onPlan: () => void
}

export function MenuDetail({ menu, date, copy, busy, onBack, onPlan }: Props) {
  return (
    <section className="calendar-menu-detail" aria-labelledby="calendar-menu-title">
      <button type="button" className="btn plain calendar-back" onClick={onBack}>
        {copy.back}
      </button>
      <p className="calendar-section-label">{copy.weeklyMenu}</p>
      <h2 id="calendar-menu-title" className="calendar-menu-title">
        {menu.name}
      </h2>
      <p className="note">
        {copy.dateTitle(date)}
        {menu.covers ? ` · ${copy.covers(menu.covers)}` : ''}
      </p>
      <div className="calendar-recipe-list">
        {menu.dishes.map((dish, index) => (
          <article key={`${dish.name}-${index}`} className="calendar-recipe">
            <h3>{dish.name}</h3>
            <p className="calendar-recipe-label">{copy.recipe}</p>
            <p>{dish.recipe?.trim() || copy.noRecipe}</p>
          </article>
        ))}
      </div>
      <button type="button" className="btn calendar-plan" disabled={busy} onClick={onPlan}>
        {busy ? copy.planning : copy.planCart}
      </button>
    </section>
  )
}
