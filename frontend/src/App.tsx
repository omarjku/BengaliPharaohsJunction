import { useEffect, useState } from 'react'
import { api } from './api'

type Health = { status: string; valio_key_configured: boolean; gemini_key_configured: boolean }

// Placeholder shell: proves frontend ↔ backend wiring. Real UI is T08 / T17.
export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Health>('/api/health').then(setHealth).catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main>
      <h1>Valio Aimo Front Door</h1>
      {error && <p role="alert">Backend unreachable: {error}</p>}
      {health && (
        <ul>
          <li>Backend: {health.status}</li>
          <li>Valio key: {health.valio_key_configured ? 'configured' : 'missing'}</li>
          <li>Gemini key: {health.gemini_key_configured ? 'configured' : 'missing'}</li>
        </ul>
      )}
      {!health && !error && <p>Checking backend…</p>}
    </main>
  )
}
