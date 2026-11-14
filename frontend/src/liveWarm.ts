import { useEffect } from 'react'
import { getKeys, MOCK, openLive } from './api'
import type { LiveEvent, LiveSocket } from './types'

type LiveConnection = Pick<LiveSocket, 'send' | 'close'>
type LiveHandlers = Pick<LiveSocket, 'onEvent' | 'onClose'>

const WARM_MS = 45000

type WarmSlot = {
  promise: Promise<LiveConnection>
  socket: LiveConnection | null
  events: LiveEvent[]
  handlers: LiveHandlers
  ready: boolean
  closed: boolean
  taken: boolean
  timer: ReturnType<typeof setTimeout> | null
}

let warmSlot: WarmSlot | null = null

function clearWarmSlot(slot: WarmSlot) {
  if (warmSlot === slot) warmSlot = null
  if (slot.timer !== null) {
    clearTimeout(slot.timer)
    slot.timer = null
  }
}

function closeWarmSlot(slot: WarmSlot) {
  slot.closed = true
  clearWarmSlot(slot)
  slot.socket?.close()
}

export function warmLive() {
  if (MOCK || typeof document === 'undefined' || document.hidden || !getKeys().agentKey || warmSlot) return

  let resolveConnection: (socket: LiveConnection) => void = () => {}
  let rejectConnection: (reason?: unknown) => void = () => {}
  const promise = new Promise<LiveConnection>((resolve, reject) => {
    resolveConnection = resolve
    rejectConnection = reject
  })
  let slot: WarmSlot | null = null
  const buffering: LiveHandlers = {
    onEvent: (event) => {
      const current = slot
      if (!current) return
      if (current.taken) return current.handlers.onEvent(event)
      if (current.closed) return
      current.events.push(event)
      if (event.type === 'ready') current.ready = true
    },
    onClose: () => {
      const current = slot
      if (!current) return
      current.closed = true
      if (current.taken) current.handlers.onClose()
      else clearWarmSlot(current)
    },
  }
  const current: WarmSlot = {
    promise,
    socket: null,
    events: [],
    handlers: buffering,
    ready: false,
    closed: false,
    taken: false,
    timer: null,
  }
  slot = current
  warmSlot = current
  void promise.then(
    (socket) => {
      current.socket = socket
      if (current.closed) socket.close()
    },
    () => {
      current.closed = true
      clearWarmSlot(current)
    },
  )
  current.timer = setTimeout(() => closeWarmSlot(current), WARM_MS)
  try {
    const source = openLive(buffering)
    void source.then(resolveConnection, rejectConnection)
  } catch (err) {
    rejectConnection(err)
  }
}

export function takeLive(handlers: LiveHandlers): Promise<LiveConnection> {
  const slot = warmSlot
  if (!slot || slot.closed) {
    if (slot) clearWarmSlot(slot)
    return openLive(handlers)
  }

  clearWarmSlot(slot)
  slot.taken = true
  slot.handlers = handlers
  const buffered = slot.events.splice(0)
  buffered.forEach((event) => handlers.onEvent(event))
  return slot.promise
}

export function dropWarm() {
  if (warmSlot) closeWarmSlot(warmSlot)
}

export function useLiveWarm(enabled: boolean) {
  useEffect(() => {
    if (!enabled) {
      dropWarm()
      return
    }

    const onVisibilityChange = () => {
      if (document.hidden) dropWarm()
      else warmLive()
    }
    const onFocus = () => warmLive()
    // A touch or key press on the page means talking may be next: re-warm if the idle socket has expired (a no-op
    // while one is warm).
    const onActivity = () => warmLive()

    if (!document.hidden) warmLive()
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', onFocus)
    window.addEventListener('pointerdown', onActivity, { passive: true })
    window.addEventListener('keydown', onActivity, { passive: true })
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('pointerdown', onActivity)
      window.removeEventListener('keydown', onActivity)
      dropWarm()
    }
  }, [enabled])
}
