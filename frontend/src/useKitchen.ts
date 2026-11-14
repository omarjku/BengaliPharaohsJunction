import { useEffect, useState } from 'react'
import { getProfile, MOCK } from './api'

// Which kitchen this device is signed in as: the agent key's own buyer id (GET /api/profile), re-read whenever the key
// changes (a setup link or the keys sheet). null while unknown. Also keys the "onboarding skipped" flag per kitchen.
export function useKitchen(agentKey: string): string | null {
  const [id, setId] = useState<string | null>(null)
  useEffect(() => {
    setId(null) // a different key: don't keep showing the old kitchen
    if (!MOCK && !agentKey) return
    let live = true
    getProfile().then(
      (p) => live && setId(p.buyer_id),
      () => live && setId(null),
    )
    return () => {
      live = false
    }
  }, [agentKey])
  return id
}

const skipKey = (kitchen: string) => `valio-aimo-onboarding-skipped:${kitchen}`
export const onboardingSkippedFor = (kitchen: string): boolean => {
  try {
    return localStorage.getItem(skipKey(kitchen)) === '1'
  } catch {
    return false
  }
}
export const skipOnboardingFor = (kitchen: string) => {
  try {
    localStorage.setItem(skipKey(kitchen), '1')
  } catch {
    // storage blocked: skipped for this page only (the caller keeps its own state)
  }
}
