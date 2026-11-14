import type { AgentRun, AuditEntry, Health, OrderResponse, RunInput } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

// Mock mode (fixtures, no backend): VITE_MOCK=1 at build time, or ?mock=1 on the dev server only.
// In a production build without VITE_MOCK this folds to `false`, so the dynamic import below is dead code and the
// fixtures are not bundled.
export const MOCK =
  import.meta.env.VITE_MOCK === '1' ||
  (import.meta.env.DEV && new URLSearchParams(window.location.search).get('mock') === '1')

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error("Can't reach the backend. Is it running?")
  }
  if (!res.ok) throw new Error(`Request failed (${res.status}): ${await errorDetail(res)}`)
  try {
    return (await res.json()) as T
  } catch {
    throw new Error('Backend returned an unexpected response.')
  }
}

// FastAPI errors look like {"detail": "..."} or {"detail": [{"msg": "..."}]}; never show raw bodies.
async function errorDetail(res: Response): Promise<string> {
  try {
    const { detail } = await res.json()
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const msgs = detail.map((d) => d?.msg).filter((m): m is string => typeof m === 'string')
      return msgs.length ? msgs.join('; ') : 'invalid request'
    }
  } catch {
    // not JSON
  }
  return res.statusText || 'unexpected error'
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })
const mock = () => import('./mock').then((m) => m.mockApi)

export const getHealth = () => (MOCK ? mock().then((m) => m.health()) : api<Health>('/api/health'))

export const runAgent = (input: RunInput) =>
  MOCK ? mock().then((m) => m.run(input)) : api<AgentRun>('/api/agent/run', post(input))

export const decideOrder = (orderId: string, action: 'approve' | 'reject', approver: string) =>
  MOCK
    ? mock().then((m) => m.decide(orderId, action, approver))
    : api<OrderResponse>(`/api/orders/${encodeURIComponent(orderId)}/${action}`, post({ approver }))

export const getAudit = (buyerId: string) =>
  MOCK ? mock().then((m) => m.audit(buyerId)) : api<AuditEntry[]>(`/api/audit?buyer_id=${encodeURIComponent(buyerId)}`)
