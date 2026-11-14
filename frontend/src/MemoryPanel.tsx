import { useEffect, useState } from 'react'
import { forgetMemory, getKeys, getProfile, MOCK } from './api'
import { errorText } from './format'
import { useCopy } from './i18n'
import type { BuyerProfile } from './types'
import './MemoryPanel.css'

// "What I know about your kitchen": the buyer profile (GET /api/profile, agent key). Standing dietary needs, and every
// remembered preference with its scope ("this order only" / "always") and why it is used; Revoke forgets one
// (DELETE /api/profile/memories/{id}, approver key: forgetting is the chef's call). Guidance, never rules.
export function MemoryPanel({ refreshKey = 0, onUpdateKitchen }: { refreshKey?: number; onUpdateKitchen?: () => void }) {
  const c = useCopy()
  const t = c.UI.rules
  const { agentKey, approverKey } = getKeys()
  const [profile, setProfile] = useState<BuyerProfile | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null) // the memory being revoked
  const [error, setError] = useState<string | null>(null)
  const [opened, setOpened] = useState(0) // reload each time it's opened: a choice remembered on the order screen shows up
  useEffect(() => {
    if (!MOCK && !agentKey) return
    let cancelled = false
    getProfile().then(
      (p) => !cancelled && setProfile(p),
      () => !cancelled && setFailed(true),
    )
    return () => {
      cancelled = true
    }
  }, [agentKey, refreshKey, opened])

  async function revoke(id: string) {
    setBusy(id)
    setError(null)
    try {
      setProfile(await forgetMemory(id))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  if (!profile && !failed) return null
  const memories = profile?.memories ?? []
  const empty = profile && !profile.dietary.length && !memories.length && !profile.usual_product_ids.length
  const canRevoke = MOCK || !!approverKey
  return (
    <div className="more flush">
      <details onToggle={(e) => e.currentTarget.open && setOpened((n) => n + 1)}>
        <summary>{t.know}</summary>
        <ul className="more-body">
          {failed && <li className="quiet">{t.knowFailed}</li>}
          {profile && <li className="quiet small">{t.knowNote}</li>}
          {profile?.dietary.map((d) => (
            <li key={d.tag}>
              <p>
                {t.knowDiet}: {d.label}
              </p>
              <p className="quiet small">{d.because}</p>
            </li>
          ))}
          {memories.map((m) => (
            <li key={m.id} className="mem-row">
              <div className="mem-main">
                <p>
                  {m.text} <span className="mem-tag">{t.scope[m.scope] ?? m.scope.replace(/_/g, ' ')}</span>
                </p>
                {m.used_because && <p className="quiet small">{m.used_because}</p>}
              </div>
              {canRevoke && (
                <button type="button" className="btn plain mem-revoke" onClick={() => void revoke(m.id)} disabled={busy !== null}>
                  {busy === m.id ? t.revoking : t.revoke}
                </button>
              )}
            </li>
          ))}
          {profile && profile.usual_product_ids.length > 0 && <li className="quiet">{t.knowUsual(profile.usual_product_ids.length)}</li>}
          {empty && <li className="quiet">{t.knowNothing}</li>}
          {!canRevoke && memories.length > 0 && <li className="quiet small">{t.revokeNeedsKey}</li>}
          {onUpdateKitchen && (
            <li>
              <button type="button" className="btn plain accent-text" onClick={onUpdateKitchen}>
                {t.updateKitchen}
              </button>
            </li>
          )}
          {error && (
            <li className="problem" role="alert">
              {error}
            </li>
          )}
        </ul>
      </details>
    </div>
  )
}
