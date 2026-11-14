import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { useState } from 'react'
import App from './App.tsx'
import Landing from './Landing.tsx'

function Root() {
  const skip = new URLSearchParams(location.search).has('app')
  const [entered, setEntered] = useState(() => skip || import.meta.env.MODE === 'test' || sessionStorage.getItem('fd-entered') === '1')
  const [leaving, setLeaving] = useState(false)
  function enter() {
    sessionStorage.setItem('fd-entered', '1')
    setLeaving(true)
    setTimeout(() => setEntered(true), matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 380)
  }
  if (!entered) return <Landing onEnter={enter} leaving={leaving} />
  return (
    <div className={leaving ? 'app-in' : undefined}>
      <App />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
