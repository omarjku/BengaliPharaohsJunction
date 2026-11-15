import type { ReactNode } from 'react'
import { useCopy } from './i18n'
import type { Choice } from './types'
import './Conversation.css'

export type VoiceLayout = 'orb' | 'thread'

// V2 questions send the visible label back as the answer, not an index hidden from the chef.
export function ChoiceChips({ choices, onChoose, disabled = false }: {
  choices: Choice[]
  onChoose: (label: string) => void
  disabled?: boolean
}) {
  const t = useCopy().UI.question
  if (!choices.length) return null
  return (
    <div className="chips" role="group" aria-label={t.options}>
      {choices.map((choice) => (
        <button key={choice.label} type="button" className="chip" onClick={() => onChoose(choice.label)} disabled={disabled}>
          {choice.label}
        </button>
      ))}
    </div>
  )
}

// The conversation screen's layout, three modes in one thread:
// - text only: the thread, the bar at the bottom
// - voice only: the thread hidden, the big orb in the middle
// - voice + text: the thread, a small orb docked above the bar
// Tapping the orb, or the labelled toggle, switches the voice layouts. Logic lives in App; this only arranges.
export function Conversation({ voiceOn, layout, onToggle, thread, bigOrb, smallOrb, status, cartDock, composer }: {
  voiceOn: boolean
  layout: VoiceLayout
  onToggle: () => void
  thread: ReactNode
  bigOrb: ReactNode
  smallOrb: ReactNode
  status: ReactNode // the voice status line (listening, the tool running, an error)
  cartDock?: ReactNode
  composer: ReactNode
}) {
  const t = useCopy().UI.conv
  const showThread = !voiceOn || layout === 'thread'
  return (
    <div className={`conv${voiceOn ? ` voice-on voice-${layout}` : ''}${cartDock ? ' has-cart' : ''}`}>
      {voiceOn && (
        <div className="conv-toggle">
          <button type="button" className="link" aria-pressed={layout === 'thread'} onClick={onToggle}>
            {layout === 'orb' ? t.showThread : t.voiceOnly}
          </button>
        </div>
      )}
      <div className="conv-thread" hidden={!showThread}>
        {thread}
      </div>
      {voiceOn && layout === 'orb' && (
        <div className="conv-stage">
          {bigOrb}
          <div className="conv-status">{status}</div>
        </div>
      )}
      <div className="conv-bar">
        {voiceOn && layout === 'thread' && (
          <div className="conv-dock">
            {smallOrb}
            <div className="conv-status">{status}</div>
          </div>
        )}
        {cartDock && <div className="conv-cart-dock">{cartDock}</div>}
        {composer}
      </div>
    </div>
  )
}
