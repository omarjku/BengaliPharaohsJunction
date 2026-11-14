import { useEffect, useRef, type FormEvent, type KeyboardEvent, type ReactNode, type Ref } from 'react'
import { useCopy } from './i18n'
import './Composer.css'

// The bottom bar, one rounded pill: [+] photo, the text field, then either the dictation mic and the voice button
// (text only) or mute and X (voice on). Enter sends; Shift+Enter is a new line. Layout only: the parent decides.
export function Composer(p: {
  voiceOn: boolean
  text: string
  setText: (t: string) => void
  onSend: (text: string) => void
  placeholder: string
  busy: boolean
  photo: ReactNode // <PhotoButton variant="icon" />
  mic: ReactNode // dictation (text only)
  onVoice: (() => void) | null // start the voice conversation; null when Talk isn't available
  muted: boolean
  onMute: () => void
  onEnd: () => void
  fieldRef: Ref<HTMLTextAreaElement>
}) {
  const t = useCopy().UI.conv
  const local = useRef<HTMLTextAreaElement | null>(null)
  // The field grows with the text, up to about five lines.
  useEffect(() => {
    const f = local.current
    if (!f) return
    f.style.height = 'auto'
    f.style.height = `${Math.min(f.scrollHeight, 140)}px`
  }, [p.text])
  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (p.text.trim() && !p.busy) p.onSend(p.text.trim())
  }
  function key(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }
  return (
    <form className={`composer${p.voiceOn ? ' voice-on' : ''}${p.text.trim() ? ' has-text' : ''}`} onSubmit={submit}>
      {p.photo}
      <label className="sr-only" htmlFor="text">
        {t.field}
      </label>
      <textarea
        id="text"
        ref={(el) => {
          local.current = el
          if (typeof p.fieldRef === 'function') p.fieldRef(el)
          else if (p.fieldRef) (p.fieldRef as { current: HTMLTextAreaElement | null }).current = el
        }}
        className="composer-field"
        rows={1}
        value={p.text}
        onChange={(e) => p.setText(e.target.value)}
        onKeyDown={key}
        placeholder={p.placeholder}
        enterKeyHint="send"
      />
      <span className={`composer-slot${p.onVoice && !p.voiceOn ? ' with-voice' : ''}`}>
        <button type="submit" className="composer-btn composer-send" aria-label={t.send} title={t.send} disabled={p.busy} tabIndex={p.text.trim() ? undefined : -1} aria-hidden={p.text.trim() ? undefined : true} inert={!p.text.trim()}>
          <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
            <path d="M10 16V4M4.5 9.5 10 4l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {p.onVoice && !p.voiceOn && (
          <button type="button" className="composer-btn composer-voice" aria-label={t.voice} title={t.voice} onClick={p.onVoice} disabled={p.busy} tabIndex={p.text.trim() ? -1 : undefined} aria-hidden={p.text.trim() ? true : undefined} inert={!!p.text.trim()}>
            <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
              <path d="M4 8v4M7.3 5v10M10.6 7v6M13.9 4v12M17 8v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </span>
      {p.voiceOn ? (
        <>
          <button type="button" className={`composer-btn${p.muted ? ' on' : ''}`} aria-pressed={p.muted} aria-label={p.muted ? t.unmute : t.mute} title={p.muted ? t.unmute : t.mute} onClick={p.onMute}>
            <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
              <rect x="7" y="2" width="6" height="10" rx="3" fill="currentColor" />
              <path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              {p.muted && <path d="M3 3l14 14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />}
            </svg>
          </button>
          <button type="button" className="composer-btn composer-end" aria-label={t.end} title={t.end} onClick={p.onEnd}>
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
              <path d="M5 5l10 10M15 5 5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </>
      ) : (
        <>
          {!p.text.trim() && p.mic}
        </>
      )}
    </form>
  )
}
