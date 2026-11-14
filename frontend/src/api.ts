import { mockApi } from './mock'
import type { AgentRun, ApprovalResult, AuditEntry, Health, RunInput } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

// Mock mode: VITE_MOCK=1 at build time, or ?mock=1 in the URL. Uses fixtures, no backend needed.
export const MOCK =
  import.meta.env.VITE_MOCK === '1' || new URLSearchParams(window.location.search).get('mock') === '1'

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
  return res.json() as Promise<T>
}

// FastAPI errors look like {"detail": "..."} or {"detail": [{"msg": "..."}]}; never show raw bodies.
async function errorDetail(res: Response): Promise<string> {
  try {
    const { detail } = await res.json()
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  } catch {
    // not JSON
  }
  return res.statusText || 'unexpected error'
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const getHealth = () => (MOCK ? mockApi.health() : api<Health>('/api/health'))

export const runAgent = (input: RunInput) =>
  MOCK ? mockApi.run(input) : api<AgentRun>('/api/agent/run', post(input))

export const decideOrder = (orderId: string, action: 'approve' | 'reject') =>
  MOCK
    ? mockApi.decide(orderId, action)
    : api<ApprovalResult>(`/api/orders/${encodeURIComponent(orderId)}/${action}`, { method: 'POST' })

export const getAudit = (buyerId: string) =>
  MOCK ? mockApi.audit() : api<AuditEntry[]>(`/api/audit?buyer_id=${encodeURIComponent(buyerId)}`)
