import { memo, useRef, useState } from 'react'
import { Dithering } from '@paper-design/shaders-react'

const Shader = memo(Dithering)

const SWING_MS = 600

/** First screen: dark, a dithered teal door that is the way in, the app name in pixel type. */
export default function Landing({ onEnter, leaving = false }: { onEnter: () => void; leaving?: boolean }) {
  const [open, setOpen] = useState(false)
  const done = useRef(false)
  const drag = useRef<number | null>(null)

  const openDoor = () => {
    if (done.current) return
    done.current = true
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onEnter()
      return
    }
    setOpen(true)
    setTimeout(onEnter, SWING_MS)
  }

  return (
    <section className={`landing${leaving ? ' leaving' : ''}`}>
      <div className="landing-copy">
        <h1 className="landing-name">
          Front
          <br />
          Door
        </h1>
        <p className="landing-text">
          Tell it what the kitchen needs, in your own words. It checks Valio’s stock and prices, orders what is
          safe, and asks you before anything else.
        </p>
      </div>
      <div className="landing-stage">
        <button
          type="button"
          className={`door${open ? ' open' : ''}`}
          aria-label="Open Front Door"
          onClick={openDoor}
          onPointerDown={(e) => {
            drag.current = e.clientX
          }}
          onPointerUp={(e) => {
            if (drag.current !== null && Math.abs(e.clientX - drag.current) > 40) openDoor()
            drag.current = null
          }}
        >
          <span className="door-light" aria-hidden="true" />
          <span className="door-leaf" aria-hidden="true">
            <Shader
              colorBack="#000000"
              colorFront="#4cc3e3"
              shape="simplex"
              type="4x4"
              size={2}
              speed={0.6}
              scale={2}
              style={{ width: '100%', height: '100%' }}
            />
            <span className="door-handle" />
          </span>
        </button>
        <p className="door-hint" aria-hidden="true">
          <span className="door-hint-idle">Tap the door</span>
          <span className="door-hint-win">Come in, chef. Your kitchen is ready.</span>
        </p>
      </div>
    </section>
  )
}
