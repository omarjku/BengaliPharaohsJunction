import { useEffect, useRef, useState } from 'react'
import { useCopy } from './i18n'
import './Header.css'

type Theme = 'light' | 'dark'
const KEY = 'fd-theme'

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

// The menu button (three lines) and its panel: language and appearance. Opens and closes with a short slide and fade.
export function HeaderMenu({ onSwitchLang }: { onSwitchLang: () => void }) {
  const c = useCopy()
  const m = c.UI.hmenu
  const [open, setOpen] = useState(false)
  const [theme, setTheme] = useState<Theme>(currentTheme)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  function pick(next: Theme) {
    document.documentElement.dataset.theme = next
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // storage blocked: it lasts for this page only
    }
    setTheme(next)
  }

  return (
    <div className="hmenu" ref={root}>
      <button
        ref={button}
        type="button"
        className="hmenu-btn"
        aria-expanded={open}
        aria-controls="hmenu-panel"
        aria-label={open ? m.close : m.open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="hmenu-bars" aria-hidden="true" />
      </button>
      <div id="hmenu-panel" className={`hmenu-panel${open ? ' open' : ''}`} inert={!open}>
        <p className="hmenu-label">{m.language}</p>
        <div className="hmenu-seg" role="group" aria-label={m.language}>
          <button type="button" aria-pressed={c.LANG === 'fi'} onClick={() => c.LANG !== 'fi' && onSwitchLang()}>
            {m.fi}
          </button>
          <button type="button" aria-pressed={c.LANG === 'en'} onClick={() => c.LANG !== 'en' && onSwitchLang()}>
            {m.en}
          </button>
        </div>
        <p className="hmenu-label">{m.theme}</p>
        <div className="hmenu-seg" role="group" aria-label={m.theme}>
          <button type="button" aria-pressed={theme === 'light'} onClick={() => pick('light')}>
            {m.light}
          </button>
          <button type="button" aria-pressed={theme === 'dark'} onClick={() => pick('dark')}>
            {m.dark}
          </button>
        </div>
      </div>
    </div>
  )
}
