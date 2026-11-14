import { useRef, type KeyboardEvent, type PointerEvent } from 'react'
import type { useVoice } from './useVoice'

const HOLD_MS = 300 // shorter than this is a tap (toggle), longer is push-to-talk

// The mic button: hold to talk, tap to toggle. Keyboard (Enter/Space) toggles.
export function MicButton({ voice, disabled }: { voice: ReturnType<typeof useVoice>; disabled: boolean }) {
  const pressedAt = useRef(0)
  const listening = voice.state === 'listening'

  function down(e: PointerEvent<HTMLButtonElement>) {
    if (disabled || e.button !== 0) return
    e.preventDefault()
    if (listening) {
      voice.stop() // second tap of a toggle
      return
    }
    pressedAt.current = Date.now()
    try {
      e.currentTarget.setPointerCapture(e.pointerId) // keep the press even if the thumb slides off
    } catch {
      // not capturable (synthetic or already released): holding still works
    }
    void voice.start(false)
  }
  function up() {
    if (!pressedAt.current) return
    const held = Date.now() - pressedAt.current
    pressedAt.current = 0
    if (held >= HOLD_MS) voice.stop() // push-to-talk: release sends
    // a short tap leaves it listening (toggle); the next tap sends
  }
  function key(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== 'Enter' && e.key !== ' ') return
    e.preventDefault()
    if (listening) voice.stop()
    else void voice.start(true)
  }

  return (
    <button
      type="button"
      ref={(el) => {
        voice.levelEl.current = el
      }}
      className={`mic${listening ? ' on' : ''}${voice.state === 'thinking' ? ' busy' : ''}`}
      aria-label={listening ? 'Stop and send' : 'Order by voice: hold to talk, or press to start and again to send'}
      aria-pressed={listening}
      disabled={disabled || voice.state === 'thinking'}
      onPointerDown={down}
      onPointerUp={up}
      onPointerCancel={up}
      onKeyDown={key}
      onContextMenu={(e) => e.preventDefault()}
    >
      <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
        <rect x="7" y="2" width="6" height="10" rx="3" fill="currentColor" />
        <path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    </button>
  )
}

// What the voice is doing, in one quiet line under the box.
export function VoiceStatus({ voice }: { voice: ReturnType<typeof useVoice> }) {
  if (voice.state === 'intro')
    return (
      <div className="voice-note" role="dialog" aria-label="Order by voice">
        <p>Hold to order by voice. Audio is only used to transcribe this request.</p>
        <div className="actions">
          <button type="button" className="btn" onClick={voice.acceptIntro}>
            Start talking
          </button>
          <button type="button" className="btn plain" onClick={voice.dismiss}>
            Not now
          </button>
        </div>
      </div>
    )
  const line =
    voice.state === 'listening'
      ? voice.mode === 'hold'
        ? 'Listening… let go to send.'
        : 'Listening… tap the mic to send.'
      : voice.state === 'thinking'
        ? 'Thinking…'
        : (voice.state === 'denied' || voice.state === 'error') && voice.message
          ? voice.message
          : null
  return (
    <p className={`voice-status${voice.state === 'listening' ? ' live' : ''}`} role="status">
      {line}
    </p>
  )
}

