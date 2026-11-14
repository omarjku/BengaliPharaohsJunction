import type { RefObject } from 'react'

type Props = {
  date: string
  label: string
  open: boolean
  hasItems: boolean
  onClick: () => void
  buttonRef?: RefObject<HTMLButtonElement | null>
}

export function CalendarIcon({ date, label, open, hasItems, onClick, buttonRef }: Props) {
  const day = Number(date.slice(-2)).toString()
  return (
    <button
      ref={buttonRef}
      type="button"
      className="calendar-icon"
      aria-label={label}
      aria-expanded={open}
      aria-controls="calendar-sheet"
      onClick={onClick}
    >
      <span className="calendar-icon-glyph" aria-hidden="true">
        <span className="calendar-icon-number">{day}</span>
      </span>
      {hasItems && <span className="calendar-icon-dot" aria-hidden="true" />}
    </button>
  )
}
