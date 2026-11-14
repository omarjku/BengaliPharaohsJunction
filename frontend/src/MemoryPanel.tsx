import { useEffect, useState, type CSSProperties } from 'react'
import { KcDialog } from './KcCards'
import { forgetMemory, getKeys, getProfile, MOCK } from './api'
import { useCopy } from './i18n'
import type { BuyerProfile, Memory } from './types'
import './MemoryPanel.css'
import './KitchenCards.css'

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
  const [openId, setOpenId] = useState<string | null>(null)

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

  const selected: Selected | null = (() => {
    if (!openId) return null
    if (openId.startsWith('diet:')) {
      const diet = profile.dietary.find((d) => `diet:${d.tag}` === openId)
      return diet ? { id: openId, title: `${t.dietary}: ${diet.label}`, scope: null, detail: diet.because, source: t.source.profile, memoryId: null } : null
    }
    const memory = memories.find((m) => `mem:${m.id}` === openId)
    return memory
      ? { id: openId, title: memory.text, scope: t.scope[memory.scope] ?? memory.scope.replace(/_/g, ' '), detail: memory.used_because ?? null, source: sourceFor(memory), memoryId: memory.id }
      : null
  })()

  return (
    <div className="more flush kitchen-memory">
      <ul className="more-body">
        <li className="quiet small">{t.factsNote}</li>
      </ul>
      {profile.dietary.length > 0 && (
        <section className="kc-group">
          <h3 className="kc-heading">{t.dietary}</h3>
          <ul className="kc-grid">
            {profile.dietary.map((diet, i) => (
              <li key={diet.tag} style={{ '--kc-i': i } as CSSProperties}>
                <button type="button" className="kc-card" onClick={() => setOpenId(`diet:${diet.tag}`)} aria-haspopup="dialog">
                  <span className="kc-card-title">{diet.label}</span>
                  <span className="kc-chip">{t.dietary}</span>
                  <span className="kc-card-line">{diet.because}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {memories.length > 0 && (
        <section className="kc-group">
          <h3 className="kc-heading">{t.kcRemembered}</h3>
          <ul className="kc-grid">
            {memories.map((memory, i) => (
              <li key={memory.id} style={{ '--kc-i': i } as CSSProperties}>
                <button type="button" className="kc-card" onClick={() => setOpenId(`mem:${memory.id}`)} aria-haspopup="dialog">
                  <span className="kc-card-title">{memory.text}</span>
                  <span className="kc-chip">{t.scope[memory.scope] ?? memory.scope.replace(/_/g, ' ')}</span>
                  {memory.used_because && <span className="kc-card-line">{memory.used_because}</span>}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <ul className="more-body">
        {historyProducts.length > 0 && <li className="quiet">{t.usualFromHistory(historyProducts.length)}</li>}
        {empty && <li className="quiet">{t.factsNothing}</li>}
        {!canRevoke && memories.length > 0 && <li className="quiet small">{t.revokeNeedsKey}</li>}
        {error && (
          <li className="problem" role="alert">
            {error}
          </li>
        )}
      </ul>
      {selected && (
        <KcDialog key={selected.id} onClose={() => setOpenId(null)} title={selected.title} closeLabel={t.kcClose}>
          {selected.scope && <p><span className="mem-tag">{selected.scope}</span></p>}
          {selected.detail && <p className="quiet small">{selected.detail}</p>}
          <p className="quiet small mem-source">{t.kcSource(selected.source)}</p>
          {selected.memoryId && canRevoke && (
            <button type="button" className="btn plain mem-revoke" onClick={() => void revoke(selected.memoryId as string)} disabled={busy !== null}>
              {busy === selected.memoryId ? t.revoking : t.revoke}
            </button>
          )}
        </KcDialog>
      )}
    </div>
  )
}

type Selected = { id: string; title: string; scope: string | null; detail: string | null; source: string; memoryId: string | null }
