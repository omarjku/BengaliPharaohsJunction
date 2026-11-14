import { useEffect, useState } from 'react'
import { forgetMemory, getKeys, getProfile, MOCK } from './api'
import { useCopy } from './i18n'
import type { BuyerProfile, Memory } from './types'
import './MemoryPanel.css'

// The flat profile list for Kitchen: standing dietary needs, remembered preferences and the product-history count.
// Revoke is the chef's call, so it uses the approver key even though the profile itself is read with the agent key.
export function MemoryPanel({ refreshKey = 0, reloadKey = 0 }: { refreshKey?: number; reloadKey?: number }) {
  const c = useCopy()
  const t = c.UI.kitchen
  const { agentKey, approverKey } = getKeys()
  const [profile, setProfile] = useState<BuyerProfile | undefined>(undefined)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setProfile(undefined)
    setFailed(false)
    setError(null)
    if (!MOCK && !agentKey) return
    let cancelled = false
    getProfile().then(
      (next) => !cancelled && setProfile(next),
      () => !cancelled && setFailed(true),
    )
    return () => {
      cancelled = true
    }
  }, [agentKey, refreshKey, reloadKey])

  async function revoke(id: string) {
    setBusy(id)
    setError(null)
    try {
      setProfile(await forgetMemory(id))
    } catch {
      setError(t.revokeFailed)
    } finally {
      setBusy(null)
    }
  }

  if (!MOCK && !agentKey) return <p className="quiet">{t.factsNeedKey}</p>
  if (!profile) return <p className="quiet">{failed ? t.factsFailed : t.factsLoading}</p>

  const memories = profile.memories
  const canRevoke = MOCK || !!approverKey
  const usualMemoryIds = new Set(
    memories
      .filter((memory) => memory.kind === 'usual_product')
      .flatMap((memory) => [memory.product_id, memory.key].filter((id): id is string => !!id)),
  )
  const historyProducts = profile.usual_product_ids.filter((id) => !usualMemoryIds.has(id))
  const empty = !profile.dietary.length && !memories.length && !historyProducts.length

  function sourceFor(memory: Memory): string {
    const date = memory.created_at && !Number.isNaN(Date.parse(memory.created_at)) ? c.longDay(memory.created_at) : t.source.dateMissing
    if (memory.source === 'onboarding') return t.source.onboarding
    if (memory.source === 'answered_question') return t.source.chat(date)
    if (memory.source === 'chosen_alternative') return t.source.choice(date)
    return t.source.unknown
  }

  return (
    <div className="more flush kitchen-memory">
      <ul className="more-body">
        <li className="quiet small">{t.factsNote}</li>
        {profile.dietary.map((diet) => (
          <li key={diet.tag} className="mem-fact">
            <p>
              {t.dietary}: {diet.label}
            </p>
            <p className="quiet small">{diet.because}</p>
            <p className="quiet small mem-source">{t.sourceLine(t.source.profile)}</p>
          </li>
        ))}
        {memories.map((memory) => (
          <li key={memory.id} className="mem-row">
            <div className="mem-main">
              <p>
                {memory.text} <span className="mem-tag">{t.scope[memory.scope] ?? memory.scope.replace(/_/g, ' ')}</span>
              </p>
              {memory.used_because && <p className="quiet small">{memory.used_because}</p>}
              <p className="quiet small mem-source">{t.sourceLine(sourceFor(memory))}</p>
            </div>
            {canRevoke && (
              <button type="button" className="btn plain mem-revoke" onClick={() => void revoke(memory.id)} disabled={busy !== null}>
                {busy === memory.id ? t.revoking : t.revoke}
              </button>
            )}
          </li>
        ))}
        {historyProducts.length > 0 && <li className="quiet">{t.usualFromHistory(historyProducts.length)}</li>}
        {empty && <li className="quiet">{t.factsNothing}</li>}
        {!canRevoke && memories.length > 0 && <li className="quiet small">{t.revokeNeedsKey}</li>}
        {error && (
          <li className="problem" role="alert">
            {error}
          </li>
        )}
      </ul>
    </div>
  )
}
