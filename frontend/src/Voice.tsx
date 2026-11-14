import { useRef, type KeyboardEvent, type PointerEvent } from 'react'
import { useCopy } from './i18n'
import { transcribe } from './api'
import { unlockSpeech, useVoice } from './useVoice'
import './Voice.css'

const HOLD_MS = 300 // shorter than this is a tap (toggle), longer is push-to-talk

// The mic button: hold to talk, tap to toggle (mouse); tap to start, tap to send (touch: a hold fights scrolling,
// the callout menu and the permission prompt on phones). Keyboard (Enter/Space) toggles.
export function MicButton({ voice, disabled }: { voice: ReturnType<typeof useVoice>; disabled: boolean }) {
  const pressedAt = useRef(0)
  const listening = voice.state === 'listening'
  const t = useCopy().UI.voice

  function down(e: PointerEvent<HTMLButtonElement>) {
    if (disabled || e.button !== 0) return
    e.preventDefault()
    unlockSpeech() // inside the gesture, so iOS lets the read-back speak later
    if (listening) {
      voice.stop() // second tap of a toggle
      return
    }
    if (e.pointerType === 'touch') {
      void voice.start(true) // phones: tap to start, tap again to send
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
    unlockSpeech()
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
      aria-label={listening ? t.stop : t.mic}
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
  const u = useCopy().UI
  const t = u.voice
  if (voice.state === 'listening' && voice.mode === 'answer')
    return (
      <p className="voice-status live" role="status">
        {u.question.listening}{' '}
        <button type="button" className="link accent inline" onClick={voice.cancel}>
          {u.question.cancel}
        </button>
      </p>
    )
  if (voice.state === 'intro')
    return (
      <div className="voice-note" role="dialog" aria-label={t.mic}>
        <p>{t.intro}</p>
        <div className="actions">
          {/* the note answers the mic press, so keyboard focus follows it */}
          <button type="button" className="btn" onClick={() => (unlockSpeech(), voice.acceptIntro())} autoFocus>
            {t.start}
          </button>
          <button type="button" className="btn plain" onClick={voice.dismiss}>
            {t.notNow}
          </button>
        </div>
      </div>
    )
  const line =
    voice.state === 'listening'
      ? voice.mode === 'hold'
        ? t.hold
        : t.toggle
      : voice.state === 'thinking'
        ? t.thinking
        : voice.state === 'denied'
          ? t.blocked
          : voice.state === 'error'
            ? (voice.message ?? t.failed) // a transcription error carries its own words; a mic failure doesn't
            : null
  return (
    <p className={`voice-status${voice.state === 'listening' ? ' live' : ''}`} role="status">
      {line}
    </p>
  )
}


// The one voice button for the order box: opens Talk (the spoken conversation) when the backend offers it, and is
// the push-to-talk mic otherwise. Same size and place as the mic, inside the text box.
export function VoiceButton({ voice, talk, disabled }: {
  voice: ReturnType<typeof useVoice>
  talk: { available: boolean; open: () => void } // from useTalkPhotoAvailable().talk and useTalk().open
  disabled: boolean
}) {
  const t = useCopy().UI.talk
  if (!talk.available) return <MicButton voice={voice} disabled={disabled} />
  return (
    <button
      type="button"
      className="mic talk-mic"
      aria-label={t.title}
      title={t.title}
      disabled={disabled}
      onClick={() => {
        unlockSpeech()
        talk.open() // inside the tap: the audio and the mic start here (iOS)
      }}
    >
      <span className="talk-mic-dot" aria-hidden="true" />
    </button>
  )
}

// A self-contained dictation mic (its own useVoice): the words go to `onText`, e.g. Onboarding's text box.
export function DictationMic({ onText, disabled = false }: { onText: (text: string) => void; disabled?: boolean }) {
  const voice = useVoice(transcribe, onText)
  return (
    <>
      <MicButton voice={voice} disabled={disabled} />
      <VoiceStatus voice={voice} />
    </>
  )
}
