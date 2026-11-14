import { useCallback, useEffect, useRef, useState } from 'react'
import { errorText } from './format'

// Push-to-talk for the one box. Hold the mic to talk and let go to send; a quick tap toggles instead (tap again
// to send), which also works from the keyboard. Audio goes to `transcribe` and nowhere else.
export type VoiceState = 'idle' | 'intro' | 'listening' | 'thinking' | 'denied' | 'error'

const INTRO_KEY = 'valio-aimo-voice-intro-seen'
const MUTE_KEY = 'valio-aimo-voice-muted'

const store = {
  get: (k: string) => {
    try {
      return localStorage.getItem(k)
    } catch {
      return null
    }
  },
  set: (k: string, v: string) => {
    try {
      localStorage.setItem(k, v)
    } catch {
      // storage blocked: it lasts for this page only
    }
  },
}

export const voiceSupported = () =>
  typeof window !== 'undefined' && typeof window.MediaRecorder !== 'undefined' && !!navigator.mediaDevices?.getUserMedia

export function useVoice(transcribe: (audio: Blob) => Promise<string>, onText: (text: string) => void) {
  const [state, setState] = useState<VoiceState>('idle')
  const [mode, setMode] = useState<'hold' | 'toggle' | 'answer'>('hold') // answer: opened by itself after a spoken question
  const [message, setMessage] = useState<string | null>(null)
  const levelEl = useRef<HTMLElement | null>(null) // the ring that breathes with the voice level
  const rec = useRef<{ recorder: MediaRecorder; stream: MediaStream; ctx: AudioContext; raf: number } | null>(null)
  const discard = useRef(false) // Cancel: stop listening and throw the recording away
  const stopWhenReady = useRef(false) // released before the recorder existed (e.g. during the permission prompt)

  function cleanup() {
    const r = rec.current
    if (!r) return
    cancelAnimationFrame(r.raf)
    r.stream.getTracks().forEach((t) => t.stop())
    void r.ctx.close()
    rec.current = null
    levelEl.current?.style.setProperty('--level', '0')
  }
  useEffect(() => cleanup, [])

  async function start(asToggle: boolean, forAnswer = false) {
    if (!store.get(INTRO_KEY)) {
      setState('intro') // explain once, before the browser asks for the microphone
      return
    }
    setMessage(null)
    setMode(forAnswer ? 'answer' : asToggle ? 'toggle' : 'hold')
    stopWhenReady.current = false
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks: Blob[] = []
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
        cleanup()
        if (discard.current) {
          discard.current = false
          setState('idle')
          return
        }
        setState('thinking')
        try {
          onText(await transcribe(blob))
          setState('idle')
        } catch (err) {
          setMessage(errorText(err))
          setState('error')
        }
      }
      // A quiet level meter: RMS of the signal, written straight to a CSS variable (no re-renders).
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      ctx.createMediaStreamSource(stream).connect(analyser)
      const data = new Uint8Array(analyser.fftSize)
      const tick = () => {
        analyser.getByteTimeDomainData(data)
        let sum = 0
        for (const v of data) sum += ((v - 128) / 128) ** 2
        const level = Math.min(1, Math.sqrt(sum / data.length) * 4)
        levelEl.current?.style.setProperty('--level', level.toFixed(2))
        if (rec.current) rec.current.raf = requestAnimationFrame(tick)
      }
      rec.current = { recorder, stream, ctx, raf: requestAnimationFrame(tick) }
      recorder.start()
      setState('listening')
      // A hold released while the browser was still asking for the mic: don't record forever, and don't send a
      // near-empty clip either. Leave it listening as a tap (toggle), so the next tap sends.
      if (stopWhenReady.current) {
        stopWhenReady.current = false
        setMode('toggle')
      }
    } catch (err) {
      cleanup()
      const denied = err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'SecurityError')
      setMessage(null) // the state ('denied' / 'error') says it; VoiceStatus words it in the chef's language
      setState(denied ? 'denied' : 'error')
    }
  }

  function stop() {
    if (rec.current && rec.current.recorder.state === 'recording') rec.current.recorder.stop()
    else stopWhenReady.current = true
  }
  function cancel() {
    if (rec.current && rec.current.recorder.state === 'recording') {
      discard.current = true
      rec.current.recorder.stop()
    } else setState('idle')
  }

  function acceptIntro() {
    store.set(INTRO_KEY, '1')
    setState('idle')
    levelEl.current?.focus() // the note's buttons vanish; keyboard focus goes back to the mic, which now stops/sends
    void start(true) // the button press is the gesture the browser needs; tap the mic again to send
  }

  return { state, mode, message, levelEl, start, stop, cancel, acceptIntro, dismiss: () => {
    setState('idle')
    levelEl.current?.focus()
  } }
}

// iOS Safari only speaks after speechSynthesis has been used inside a user gesture; the read-back comes later, after
// a fetch. So the first mic tap says an empty sentence, which unlocks it for the rest of the page.
let speechUnlocked = false
export function unlockSpeech() {
  if (speechUnlocked || typeof window === 'undefined' || !('speechSynthesis' in window)) return
  speechUnlocked = true
  speechSynthesis.speak(new SpeechSynthesisUtterance(''))
}

// Spoken read-back of the answer's first sentence, for a request made by voice. Remembered mute.
export function useReadBack() {
  const [muted, setMuted] = useState(() => store.get(MUTE_KEY) === '1')
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window
  const said = useRef('') // each sentence once, however often React re-renders
  // onEnd runs once the sentence has been said (or straight away when muted), e.g. to open the mic for an answer.
  const speak = useCallback(
    (text: string, opts: { lang?: 'fi' | 'en'; onEnd?: () => void } = {}) => {
      if (!canSpeak || muted || said.current === text) return void opts.onEnd?.()
      said.current = text
      speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(spoken(text))
      u.lang = opts.lang === 'fi' ? 'fi-FI' : 'en-GB'
      u.rate = 1.02
      if (opts.onEnd) {
        let done = false
        const end = () => !done && ((done = true), opts.onEnd!())
        u.onend = end
        u.onerror = end
      }
      speechSynthesis.speak(u)
    },
    [canSpeak, muted],
  )
  function toggle() {
    const next = !muted
    setMuted(next)
    store.set(MUTE_KEY, next ? '1' : '0')
    if (next && canSpeak) speechSynthesis.cancel()
  }
  const forget = useCallback(() => (said.current = ''), []) // a new voice request may say the same thing again
  return { muted, canSpeak, speak, toggle, forget }
}

// "€1,500" reads as "1,500 euros"; cents only when they matter.
export const spoken = (text: string) =>
  text
    .replace(/€([\d,]+)\.00\b/g, '$1 euros')
    .replace(/€([\d,]+)\.(\d\d)\b/g, '$1 euros $2')
    .replace(/€([\d,]+)/g, '$1 euros')
    .replace(/euros (order|weekly|per-line|auto-approve|limit|budget)/g, 'euro $1') // "the 1,500 euro order limit"

// The request's language, for the read-back voice (the same test the backend uses for `speak`).
export const languageOf = (text: string): 'fi' | 'en' =>
  /[äö]|\b(maito\w*|kerma\w*|voi(ta|n)?|litraa|kiloa|heti|tänään|huomenna|maanantai\w*|tarvitsen|tilaa|kpl)\b/i.test(text) ? 'fi' : 'en'
