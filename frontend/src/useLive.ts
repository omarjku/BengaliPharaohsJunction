import { useEffect, useRef, useState, type RefObject } from 'react'
import { errorText } from './format'
import { openInterviewLive, type InterviewPreview, type KitchenLiveEvent } from './kitchenEditApi'
import { takeLive } from './liveWarm'
import { shouldSendMicChunk } from './liveAudio'
import { isSessionLimitMessage, SESSION_END_MESSAGE } from './talkMessages'
import type { AskResponse, LiveEvent, LiveSocket } from './types'

// The voice conversation (WebSocket /api/live), as a hook: the conversation screen shows its words in the thread and
// its state on the orb. Mic: an AudioWorklet averaging down to 16 kHz PCM16, ~100 ms chunks (not sent while muted).
// Agent audio: 24 kHz PCM16 scheduled back to back, flushed at once on "interrupted" (barge-in). The AudioContext and
// the mic come from the tap that started voice (useTalk.open, iOS) and are stopped by useTalk.end.

export type LiveState = 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error'
export type LiveHandlers = {
  onTranscript: (role: 'user' | 'agent', text: string, final: boolean, turnId?: number, cumulative?: boolean) => void
  onResult: (r: AskResponse) => void
  onInterviewPreview?: (preview: InterviewPreview) => void
  onError: (message: string) => void
  onWarning?: (message: string) => void
  onSessionEnded?: (message: string) => void
}

const WORKLET = `
class Pcm16 extends AudioWorkletProcessor {
  constructor() { super(); this.step = sampleRate / 16000; this.pos = 0; this.sum = 0; this.n = 0; this.out = []; this.rms = 0 }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (!ch) return true
    for (let i = 0; i < ch.length; i++) {
      this.sum += ch[i]; this.n++; this.rms += ch[i] * ch[i]; this.pos++
      if (this.pos >= this.step) { this.pos -= this.step; this.out.push(this.sum / this.n); this.sum = 0; this.n = 0 }
    }
    if (this.out.length >= 1600) {
      const pcm = new Int16Array(this.out.length)
      for (let i = 0; i < pcm.length; i++) pcm[i] = Math.max(-1, Math.min(1, this.out[i])) * 0x7fff
      const level = Math.min(1, Math.sqrt(this.rms / (this.out.length * this.step)) * 4)
      this.port.postMessage({ pcm: pcm.buffer, level }, [pcm.buffer])
      this.out = []; this.rms = 0
    }
    return true
  }
}
registerProcessor('pcm16', Pcm16)`
const loaded = new WeakSet<AudioContext>() // the worklet is registered once per context (StrictMode mounts twice)

const toBase64 = (buf: ArrayBuffer) => {
  const bytes = new Uint8Array(buf)
  let s = ''
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(s)
}
const fromBase64 = (b64: string) => Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0)).buffer

export function useLive(
  session: { ctx: AudioContext; mic: Promise<MediaStream> } | null,
  handlers: LiveHandlers,
  levelEl: RefObject<HTMLElement | null>, // the orb: --level follows the voice (the chef's, or the agent's while speaking)
  messages: { denied: string; closed: string },
  mode: 'order' | 'interview' = 'order',
) {
  const [state, setState] = useState<LiveState>('connecting')
  const [tool, setTool] = useState<string | null>(null) // e.g. "Checking Valio prices and stock…"
  const [muted, setMuted] = useState(false)
  const mutedRef = useRef(false)
  const socketRef = useRef<Pick<LiveSocket, 'send' | 'close'> | null>(null)
  const h = useRef(handlers)
  const m = useRef(messages)
  useEffect(() => {
    h.current = handlers
    m.current = messages
  })
  useEffect(() => {
    mutedRef.current = muted
  }, [muted])

  useEffect(() => {
    if (!session) return
    const { ctx, mic } = session
    let node: AudioWorkletNode | null = null
    let ready = false
    let ended = false
    let nextAt = 0
    let thinking = false
    let warningShown = false
    let sessionEnded = false
    let playbackLevel = 0
    let echoMutedUntil = 0
    const playing: AudioBufferSourceNode[] = []
    setState('connecting')
    setTool(null)
    const speakingNow = () => nextAt > ctx.currentTime
    const settle = () => !ended && setState(speakingNow() ? 'speaking' : thinking ? 'thinking' : 'listening')
    const flush = () => {
      playing.splice(0).forEach((s) => {
        try {
          s.stop()
        } catch {
          // already ended
        }
      })
      nextAt = 0
      settle()
    }
    const play = (b64: string) => {
      const pcm = new Int16Array(fromBase64(b64))
      if (!pcm.length) return
      const buf = ctx.createBuffer(1, pcm.length, 24000)
      const ch = buf.getChannelData(0)
      let sum = 0
      for (let i = 0; i < pcm.length; i++) {
        ch[i] = pcm[i] / 0x8000
        sum += ch[i] * ch[i]
      }
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(ctx.destination)
      const at = Math.max(ctx.currentTime + 0.04, nextAt)
      src.start(at)
      nextAt = at + buf.duration
      echoMutedUntil = Math.max(echoMutedUntil, nextAt + 0.3)
      playbackLevel = Math.min(1, Math.sqrt(sum / pcm.length) * 4)
      playing.push(src)
      src.onended = () => {
        playing.splice(playing.indexOf(src), 1)
        settle()
      }
      levelEl.current?.style.setProperty('--level', playbackLevel.toFixed(2))
      setState('speaking')
    }
    const onEvent = (e: KitchenLiveEvent) => {
      if (ended) return
      if (e.type === 'interview_preview') {
        h.current.onInterviewPreview?.(e.preview)
      } else if (e.type === 'ready') {
        ready = true
        settle()
      } else if (e.type === 'audio') play(e.data)
      else if (e.type === 'interrupted') flush()
      else if (e.type === 'transcript') {
        h.current.onTranscript(e.role, e.text, e.final, e.turn_id, e.cumulative)
        if (e.role === 'user' && e.final) thinking = true
        if (e.role === 'agent') thinking = false
        settle()
      } else if (e.type === 'tool') {
        setTool(e.status === 'running' ? e.label : null)
        thinking = e.status === 'running'
        settle()
      } else if (e.type === 'result') h.current.onResult(e.payload)
      else if (e.type === 'warning') {
        if (warningShown) return
        warningShown = true
        h.current.onWarning?.(e.message)
        if (!mutedRef.current && typeof window !== 'undefined' && 'speechSynthesis' in window) {
          window.speechSynthesis.speak(new SpeechSynthesisUtterance(e.message))
        }
      }
      else if (e.type === 'turn_complete') {
        thinking = false
        settle()
      } else if (e.type === 'error') {
        if (isSessionLimitMessage(e.message)) {
          sessionEnded = true
          h.current.onSessionEnded?.(SESSION_END_MESSAGE)
        } else h.current.onError(e.message)
        setState('error')
      }
    }

    ;(async () => {
      try {
        if (ctx.state === 'suspended') await ctx.resume()
        const socket = mode === 'interview'
          ? await openInterviewLive({ onEvent, onClose: () => !ended && !sessionEnded && (h.current.onError(m.current.closed), setState('error')) })
          : await takeLive({ onEvent: onEvent as (event: LiveEvent) => void, onClose: () => !ended && !sessionEnded && (h.current.onError(m.current.closed), setState('error')) })
        if (ended) return socket.close() // stopped while connecting
        socketRef.current = socket
        const stream = await mic
        if (!loaded.has(ctx)) {
          loaded.add(ctx)
          const url = URL.createObjectURL(new Blob([WORKLET], { type: 'text/javascript' }))
          await ctx.audioWorklet.addModule(url)
          URL.revokeObjectURL(url)
        }
        if (ended) return
        node = new AudioWorkletNode(ctx, 'pcm16')
        node.port.onmessage = ({ data }: MessageEvent<{ pcm: ArrayBuffer; level: number }>) => {
          if (!speakingNow()) levelEl.current?.style.setProperty('--level', mutedRef.current ? '0' : data.level.toFixed(2))
          if (ready && shouldSendMicChunk(data.level, playbackLevel, ctx.currentTime < echoMutedUntil, mutedRef.current))
            socketRef.current?.send({ type: 'audio', data: toBase64(data.pcm) })
        }
        // The worklet must reach the destination to run; through a muted gain, so the chef never hears themself.
        const silent = ctx.createGain()
        silent.gain.value = 0
        ctx.createMediaStreamSource(stream).connect(node)
        node.connect(silent).connect(ctx.destination)
      } catch (err) {
        const denied = err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'SecurityError')
        h.current.onError(denied ? m.current.denied : errorText(err))
        setState('error')
      }
    })()

    return () => {
      ended = true
      socketRef.current?.send({ type: 'stop' })
      socketRef.current?.close()
      socketRef.current = null
      flush()
      node?.disconnect()
    }
  }, [session, levelEl, mode])

  // Typing while voice is on: the words go over the same socket.
  const sendText = (text: string) => socketRef.current?.send({ type: 'text', text })
  return { state, tool, muted, setMuted, sendText }
}
