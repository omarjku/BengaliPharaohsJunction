import type { Ref } from 'react'
import type { LiveState } from './useLive'
import './Orb.css'

// The voice orb: big in the middle (voice only) or small, docked above the bar (voice + text). Its state comes from
// the live events; its size follows the voice level (--level, set by useLive). Tapping it switches the layout.
export function Orb({ state, size, label, onToggle, orbRef }: {
  state: LiveState
  size: 'big' | 'small'
  label: string // what tapping does, e.g. "Show the conversation"
  onToggle: () => void
  orbRef: Ref<HTMLButtonElement>
}) {
  return (
    <button ref={orbRef} type="button" className={`orb orb-${size} orb-${state}`} onClick={onToggle} aria-label={label} title={label}>
      <span className="orb-core" aria-hidden="true" />
    </button>
  )
}
