import { useEffect, useState } from 'react'
import { getHealth, MOCK, PHOTO_READY, TALK_READY } from './api'
import { voiceSupported } from './useVoice'

// Talk and the photo button, joined to App by these two hooks only (so a restyle of App can't break them).

// Which of the two the backend can do. Talk: only when /api/health says talk: true (and VITE_TALK isn't '0', and the
// browser can record); until then the voice button is plain dictation. Photo: on unless VITE_PHOTO=0 or vision: false.
export function useTalkPhotoAvailable() {
  const [caps, setCaps] = useState({ talk: MOCK && TALK_READY && voiceSupported(), photo: PHOTO_READY })
  useEffect(() => {
    let cancelled = false
    getHealth().then(
      (h) => !cancelled && setCaps({ talk: TALK_READY && voiceSupported() && (MOCK || h.talk === true), photo: PHOTO_READY && h.vision !== false }),
      () => {},
    )
    return () => {
      cancelled = true
    }
  }, [])
  return caps
}

// One Talk session at a time. open() must run inside the tap: iOS only lets audio play and the mic open from a
// user gesture. end() stops the mic and closes the audio.
export function useTalk() {
  const [session, setSession] = useState<{ ctx: AudioContext; mic: Promise<MediaStream> } | null>(null)
  function open() {
    const ctx = new AudioContext()
    void ctx.resume()
    const mic = navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
    mic.catch(() => {}) // Talk shows the error
    setSession({ ctx, mic })
  }
  function end() {
    if (!session) return
    void session.mic.then((s) => s.getTracks().forEach((tr) => tr.stop()), () => {})
    void session.ctx.close()
    setSession(null)
  }
  return { session, open, end }
}
