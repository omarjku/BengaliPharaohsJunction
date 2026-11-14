import type { Ref } from 'react'
import { Warp } from '@paper-design/shaders-react'
import type { LiveState } from './useLive'
import './Orb.css'

// The voice orb: big in the middle (voice only) or small, docked above the bar (voice + text). Its state comes from
// the live events; its size follows the voice level (--level, set by useLive). Tapping it switches the layout.
// A soft warped blob (Paper's Warp shader). The state sets its pace; the voice level scales it (--level, in Orb.css).
const CALM = ['#00607a', '#4cc3e3', '#0b5cad', '#a5e6f4']
const RED = ['#b3261e', '#ff8a80', '#7a1712', '#ffc2bb']
const PACE: Record<LiveState, { speed: number; distortion: number; swirl: number }> = {
  connecting: { speed: 0.15, distortion: 0.15, swirl: 0.4 },
  listening: { speed: 0.5, distortion: 0.2, swirl: 0.6 },
  thinking: { speed: 1.4, distortion: 0.35, swirl: 0.9 },
  speaking: { speed: 1.0, distortion: 0.3, swirl: 0.8 },
  error: { speed: 0, distortion: 0.15, swirl: 0.4 },
}

export function Orb({ state, size, label, onToggle, orbRef }: {
  state: LiveState
  size: 'big' | 'small'
  label: string // what tapping does, e.g. "Show the conversation"
  onToggle: () => void
  orbRef: Ref<HTMLButtonElement>
}) {
  const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
  return (
    <button ref={orbRef} type="button" className={`orb orb-${size} orb-${state}`} onClick={onToggle} aria-label={label} title={label}>
      <span className="orb-core" aria-hidden="true">
        <Warp
          colors={state === 'error' ? RED : CALM}
          proportion={0.5}
          softness={1}
          shape="edge"
          shapeScale={0.35}
          scale={1.1}
          {...PACE[state]}
          speed={reduced ? 0 : PACE[state].speed}
          style={{ width: '100%', height: '100%' }}
        />
      </span>
    </button>
  )
}
