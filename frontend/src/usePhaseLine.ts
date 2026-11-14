import { useCallback, useEffect, useRef, useState } from 'react'

// One calm line saying what the agent is doing. Every phase stays at least `minMs` so it can be read (the backend's
// steps can arrive milliseconds apart, and "Asking Gemini to double-check…" is worth seeing); they queue in order.
// settle() waits until the queue has been shown, so the answer doesn't snatch the last step away mid-read.
// ponytail: an unbounded queue; the backend sends at most ~6 phases, so at most ~2.4 s of catch-up.
export function usePhaseLine(minMs = 400) {
  const [phase, setPhase] = useState<string | null>(null)
  const shownAt = useRef(0)
  const queue = useRef<string[]>([])
  const timer = useRef<number | null>(null)

  const next = useCallback(() => {
    timer.current = null
    const p = queue.current.shift()
    if (p === undefined) return
    setPhase(p)
    shownAt.current = performance.now()
    if (queue.current.length) timer.current = window.setTimeout(next, minMs)
  }, [minMs])

  const push = useCallback(
    (p: string) => {
      queue.current.push(p)
      if (timer.current !== null) return
      const wait = minMs - (performance.now() - shownAt.current)
      if (wait <= 0) next()
      else timer.current = window.setTimeout(next, wait)
    },
    [minMs, next],
  )

  const settle = useCallback(async () => {
    while (timer.current !== null || queue.current.length || (shownAt.current && performance.now() - shownAt.current < minMs)) {
      await new Promise((r) => setTimeout(r, 40))
    }
  }, [minMs])

  const reset = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current)
    timer.current = null
    queue.current = []
    shownAt.current = 0
    setPhase(null)
  }, [])

  useEffect(() => () => {
    if (timer.current !== null) clearTimeout(timer.current)
  }, [])

  return { phase, push, settle, reset }
}
