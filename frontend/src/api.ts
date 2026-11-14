import type {
  AgentRun, AuditEntry, CompileResult, Health, Mandate, MenuInput, MenuRun, OrderInput, OrderResponse, RunInput, SaveResult,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

export type ApiKeys = { agentKey: string; approverKey: string }

const KEYS_STORAGE = 'valio-aimo-keys'

// ponytail: shared-secret keys in localStorage are readable by any script on this origin; fine for the demo,
// a real deployment signs approvers in instead.
function loadKeys(): ApiKeys {
  try {
    const stored = JSON.parse(localStorage.getItem(KEYS_STORAGE) ?? '{}') as Partial<ApiKeys>
    return {
      agentKey: typeof stored.agentKey === 'string' ? stored.agentKey : '',
      approverKey: typeof stored.approverKey === 'string' ? stored.approverKey : '',
    }
  } catch {
    return { agentKey: '', approverKey: '' }
  }
}

let keys: ApiKeys = loadKeys()

export const getKeys = (): ApiKeys => ({ ...keys })

export const setKeys = (next: ApiKeys) => {
  keys = { agentKey: next.agentKey.trim(), approverKey: next.approverKey.trim() }
  try {
    localStorage.setItem(KEYS_STORAGE, JSON.stringify(keys))
  } catch {
    // storage unavailable (private mode, blocked): keys last for this page only
  }
}

// Mock mode (fixtures, no backend): VITE_MOCK=1 at build time, or ?mock=1 on the dev server only.
// In a production build without VITE_MOCK this folds to `false`, so the dynamic import below is dead code and the
// fixtures are not bundled.
export const MOCK =
  import.meta.env.VITE_MOCK === '1' ||
  (import.meta.env.DEV && new URLSearchParams(window.location.search).get('mock') === '1')

type AuthRole = 'agent' | 'approver'

export async function api<T>(path: string, init?: RequestInit, authRole?: AuthRole): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error("Can't reach the backend. Is it running?")
  }
  if (!res.ok) {
    const detail = await errorDetail(res)
    if (res.status === 401 || res.status === 403) {
      if (authRole === 'agent') throw new Error(`Enter a valid agent key in Keys. ${detail}`)
      if (authRole === 'approver') throw new Error(`Approver key needed: enter it in Keys. ${detail}`)
    }
    if (res.status === 503) throw new Error(detail)
    throw new Error(`Request failed (${res.status}): ${detail}`)
  }
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
    if (typeof detail?.error === 'string') return detail.error // e.g. 409 {error, changes}, 422 {error, open_questions}
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
const keyHeader = (name: string, value: string): HeadersInit => (value ? { [name]: value } : {})

export const getHealth = () => (MOCK ? mock().then((m) => m.health()) : api<Health>('/api/health'))

export const runAgent = (input: RunInput) =>
  MOCK
    ? mock().then((m) => m.run(input))
    : api<AgentRun>('/api/agent/run', { ...post(input), headers: keyHeader('X-Agent-Key', getKeys().agentKey) }, 'agent')

export const planMenu = (input: MenuInput) =>
  MOCK
    ? mock().then((m) => m.menu(input))
    : api<MenuRun>('/api/agent/menu', { ...post(input), headers: keyHeader('X-Agent-Key', getKeys().agentKey) }, 'agent')

// Rules: approver key only (the agent key gets 401). Compile never saves; PUT saves after the chef confirms.
const approver = () => ({ 'X-Approver-Key': getKeys().approverKey })
export const getMandate = () => (MOCK ? mock().then((m) => m.getMandate()) : api<Mandate | null>('/api/mandate', { headers: approver() }, 'approver'))
export const compileRules = (text: string) =>
  MOCK ? mock().then((m) => m.compile(text)) : api<CompileResult>('/api/mandate/compile', { ...post({ text }), headers: approver() }, 'approver')
export const saveMandate = (mandate: Mandate, confirm_large_change: boolean) =>
  MOCK
    ? mock().then((m) => m.saveMandate(mandate))
    : api<SaveResult>('/api/mandate', { method: 'PUT', body: JSON.stringify({ mandate, confirm_large_change }), headers: approver() }, 'approver')

// The human picked a proposal (e.g. the split order): the agent's key places it, the front door re-checks it.
export const placeOrder = (input: OrderInput) =>
  MOCK
    ? mock().then((m) => m.place(input))
    : api<OrderResponse>('/api/orders', { ...post(input), headers: keyHeader('X-Agent-Key', getKeys().agentKey) }, 'agent')

// The approver's name lives on the stored order (signed_off_by), not in the approve/reject response.
export const getOrder = (orderId: string) =>
  MOCK
    ? mock().then((m) => m.order(orderId))
    : api<{ signed_off_by: string | null; status: OrderResponse['status'] }>(
        `/api/orders/${encodeURIComponent(orderId)}`,
        { headers: keyHeader('X-Approver-Key', getKeys().approverKey) },
        'approver',
      )

export const decideOrder = (orderId: string, action: 'approve' | 'reject') =>
  MOCK
    ? mock().then((m) => m.decide(orderId, action))
    : api<OrderResponse>(
        `/api/orders/${encodeURIComponent(orderId)}/${action}`,
        { method: 'POST', headers: keyHeader('X-Approver-Key', getKeys().approverKey) },
        'approver',
      )

export const getAudit = () =>
  MOCK
    ? mock().then((m) => m.audit())
    : api<AuditEntry[]>('/api/audit', { headers: keyHeader('X-Approver-Key', getKeys().approverKey) }, 'approver')
