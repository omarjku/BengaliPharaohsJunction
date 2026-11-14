import { useEffect, useRef, useState, type ReactNode } from 'react'
import { openLive } from './api'
import { errorText } from './format'
import { useCopy } from './i18n'
import type { AskResponse, LiveEvent, LiveSocket } from './types'

// Talk: a spoken conversation with the agent (WebSocket /api/live). One circle that listens, thinks and speaks;
// captions of both sides; the agent's tool calls in one line ("Checking Valio prices…"); the result card under them,
// so the chef approves on screen (the voice agent itself can't approve).
//
// Audio: the mic goes through an AudioWorklet that averages down to 16 kHz PCM16 and posts ~100 ms chunks; the
// agent's 24 kHz PCM16 is scheduled back to back on the same AudioContext (gapless), and flushed at once when the
// chef talks over it ("interrupted"). The AudioContext and the mic are started in the tap that opened Talk (iOS),
// and stopped by the caller when Talk ends.

type State = 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error'
type Caption = { role: 'user' | 'agent'; text: string; final: boolean }

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

export function Talk({ ctx, mic, onEnd, renderResult }: {
  ctx: AudioContext // created and resumed in the tap that opened Talk
  mic: Promise<MediaStream> // requested in that same tap
  onEnd: () => void
  renderResult: (r: AskResponse) => ReactNode
}) {
  const t = useCopy().UI.talk
  const tRef = useRef(t) // the words for errors, without restarting the conversation when the language changes
  useEffect(() => {
    tRef.current = t
  })
  const [state, setState] = useState<State>('connecting')
  const [captions, setCaptions] = useState<Caption[]>([])
  const [tool, setTool] = useState<string | null>(null)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const circle = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLButtonElement>(null)
  const log = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let socket: Pick<LiveSocket, 'send' | 'close'> | null = null
    let node: AudioWorkletNode | null = null
    let ready = false
    let ended = false
    let nextAt = 0
    let thinking = false
    const playing: AudioBufferSourceNode[] = []
    const speakingNow = () => nextAt > ctx.currentTime
    const settle = () => setState(speakingNow() ? 'speaking' : thinking ? 'thinking' : 'listening')

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
      for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(ctx.destination)
      const at = Math.max(ctx.currentTime + 0.04, nextAt)
      src.start(at)
      nextAt = at + buf.duration
      playing.push(src)
      src.onended = () => {
        playing.splice(playing.indexOf(src), 1)
        settle()
      }
      setState('speaking')
    }
    const onEvent = (e: LiveEvent) => {
      if (ended) return
      if (e.type === 'ready') {
        ready = true
        settle()
      } else if (e.type === 'audio') play(e.data)
      else if (e.type === 'interrupted') flush()
      else if (e.type === 'transcript') {
        setCaptions((cs) => {
          const last = cs[cs.length - 1]
          const next = last && last.role === e.role && !last.final ? cs.slice(0, -1) : cs
          return [...next, { role: e.role, text: e.text, final: e.final }]
        })
        if (e.role === 'user' && e.final) {
          thinking = true
          settle()
        }
        if (e.role === 'agent') thinking = false
      } else if (e.type === 'tool') {
        setTool(e.status === 'running' ? e.label : null)
        thinking = e.status === 'running'
        settle()
      } else if (e.type === 'result') setResult(e.payload)
      else if (e.type === 'turn_complete') {
        thinking = false
        settle()
      } else if (e.type === 'error') {
        setError(e.message)
        setState('error')
      }
    }

    ;(async () => {
      try {
        if (ctx.state === 'suspended') await ctx.resume()
        socket = await openLive({ onEvent, onClose: () => !ended && (setError((x) => x ?? tRef.current.closed), setState('error')) })
        if (ended) return socket.close() // unmounted while connecting
        const stream = await mic
        if (ended) return
        if (!loaded.has(ctx)) {
          loaded.add(ctx)
          const url = URL.createObjectURL(new Blob([WORKLET], { type: 'text/javascript' }))
          await ctx.audioWorklet.addModule(url)
          URL.revokeObjectURL(url)
        }
        if (ended) return
        node = new AudioWorkletNode(ctx, 'pcm16')
        node.port.onmessage = ({ data }: MessageEvent<{ pcm: ArrayBuffer; level: number }>) => {
          circle.current?.style.setProperty('--level', speakingNow() ? '0' : data.level.toFixed(2))
          if (ready) socket?.send({ type: 'audio', data: toBase64(data.pcm) })
        }
        // The worklet must reach the destination to run; through a muted gain, so the chef never hears themself.
        const mute = ctx.createGain()
        mute.gain.value = 0
        ctx.createMediaStreamSource(stream).connect(node)
        node.connect(mute).connect(ctx.destination)
      } catch (err) {
        const denied = err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'SecurityError')
        setError(denied ? tRef.current.denied : errorText(err))
        setState('error')
      }
    })()

    return () => {
      ended = true
      socket?.send({ type: 'stop' })
      socket?.close()
      flush()
      node?.disconnect() // the mic and the AudioContext belong to the caller, which stops them on End
    }
  }, [ctx, mic])

  useEffect(() => endRef.current?.focus(), [])
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: 'smooth' })
  }, [captions, result])

  const line = error ?? (state === 'connecting' ? t.connecting : tool ?? t.state[state])
  return (
    <div className="talk" role="dialog" aria-modal="true" aria-label={t.title} onKeyDown={(e) => e.key === 'Escape' && onEnd()}>
      <div className="talk-stage">
        <div ref={circle} className={`talk-circle ${state}`} aria-hidden="true" />
        <p className={`talk-line${error ? ' bad' : ''}`} role="status">
          {line}
        </p>
      </div>
      <div className="talk-log" ref={log} aria-live="polite">
        {captions.map((cap, i) => (
          <p key={i} className={`talk-caption ${cap.role}${cap.final ? '' : ' partial'}`}>
            <span className="sr-only">{cap.role === 'user' ? t.you : t.agent}: </span>
            {cap.text}
          </p>
        ))}
        {result && <div className="talk-result">{renderResult(result)}</div>}
      </div>
      <div className="talk-end">
        <button ref={endRef} type="button" className="btn" onClick={onEnd}>
          {t.end}
        </button>
      </div>
    </div>
  )
}
