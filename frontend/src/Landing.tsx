import { memo } from 'react'
import { Dithering } from '@paper-design/shaders-react'

const Shader = memo(Dithering)

/** First screen: dark, one dithered swirl, the app name in pixel type, one way in. */
export default function Landing({ onEnter }: { onEnter: () => void }) {
  return (
    <main className="landing">
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
        <button type="button" className="landing-cta" onClick={onEnter}>
          Open Front Door
        </button>
      </div>
      <div className="landing-art" aria-hidden="true">
        <Shader
          colorBack="#000000"
          colorFront="#00b3ff"
          shape="swirl"
          type="4x4"
          size={2}
          speed={0.8}
          scale={0.6}
          style={{ width: '100%', height: '100%' }}
        />
      </div>
    </main>
  )
}
