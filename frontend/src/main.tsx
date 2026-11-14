import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { useState } from 'react'
import App from './App.tsx'
import Landing from './Landing.tsx'

function Root() {
  const skip = new URLSearchParams(location.search).has('app')
  const [entered, setEntered] = useState(() => skip || import.meta.env.MODE === 'test' || sessionStorage.getItem('fd-entered') === '1')
  if (!entered) return <Landing onEnter={() => { sessionStorage.setItem('fd-entered', '1'); setEntered(true) }} />
  return <App />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
