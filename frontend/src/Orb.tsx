import { useRef, type PointerEvent, type Ref } from 'react'
import type { LiveState } from './useLive'
import './Orb.css'

const SWIPE_PX = 40 // a drag at least this long, mostly vertical, is a swipe; anything shorter is a tap

// The voice orb: big in the middle (voice only) or small, docked above the bar (voice + text). Its state comes from
// the live events; its size follows the voice level (--level, set by useLive). A tap (or Enter/Space) toggles the
// layout; a swipe up = voice only, a swipe down = voice + text (pointer events: a mouse drag works too).
export function Orb({ state, size, label, onToggle, onSwipe, orbRef }: {
  state: LiveState
  size: 'big' | 'small'
  label: string // what tapping does, e.g. "Show the conversation"
  onToggle: () => void
  onSwipe: (dir: 'up' | 'down') => void
  orbRef: Ref<HTMLButtonElement>
}) {
  const start = useRef<{ x: number; y: number } | null>(null)
  const swiped = useRef(false) // the click that follows a swipe must not also toggle

  function down(e: PointerEvent<HTMLButtonElement>) {
    start.current = { x: e.clientX, y: e.clientY }
    swiped.current = false
    try {
      e.currentTarget.setPointerCapture(e.pointerId) // keep the drag even if the finger leaves the orb
    } catch {
      // not capturable: the swipe still ends on pointerup elsewhere
    }
  }
  function up(e: PointerEvent<HTMLButtonElement>) {
    const s = start.current
    start.current = null
    if (!s) return
    const dx = e.clientX - s.x
    const dy = e.clientY - s.y
    if (Math.abs(dy) >= SWIPE_PX && Math.abs(dy) > Math.abs(dx)) {
      swiped.current = true
      onSwipe(dy < 0 ? 'up' : 'down')
    }
  }
  return (
    <button
      ref={orbRef}
      type="button"
      className={`orb orb-${size} orb-${state}`}
      onPointerDown={down}
      onPointerUp={up}
      onPointerCancel={() => (start.current = null)}
      onClick={() => {
        if (swiped.current) swiped.current = false
        else onToggle()
      }}
      aria-label={label}
      title={label}
    >
      <span className="orb-core" aria-hidden="true" />
    </button>
  )
}
