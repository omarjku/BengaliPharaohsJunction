import type {
  AgentRun, AskInput, AskResponse, AuditEntry, CompileResult, Health, Mandate, MenuInput, MenuRun, OrderInput, OrderResponse, RunInput, SaveResult,
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

// An error that keeps its HTTP status, for the few places that act on it (412: someone saved first).
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init?: RequestInit, authRole?: AuthRole): Promise<T> {
  return json<T>(await request(path, init, authRole))
}

async function json<T>(res: Response): Promise<T> {
  try {
    return (await res.json()) as T
  } catch {
    throw new Error('Backend returned an unexpected response.')
  }
}

async function request(path: string, init?: RequestInit, authRole?: AuthRole): Promise<Response> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error("Can't reach the backend. Is it running?")
  }
  if (!res.ok) throw await failure(res, authRole)
  return res
}

async function failure(res: Response, authRole?: AuthRole): Promise<ApiError> {
  const detail = await errorDetail(res)
  return failureFrom(res.status, detail, authRole)
}

function failureFrom(status: number, detail: string, authRole?: AuthRole): ApiError {
  if (status === 401 || status === 403) {
    if (authRole === 'agent') return new ApiError(status, `Enter a valid agent key in Keys. ${detail}`)
    if (authRole === 'approver') return new ApiError(status, `Approver key needed: enter it in Keys. ${detail}`)
  }
  if (status === 503) return new ApiError(503, detail)
  return new ApiError(status, `Request failed (${status}): ${detail}`)
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

// Voice: audio in, the chef's words out. The real endpoint comes from Room 3 (Gemini Live through our backend);
// until it's switched on with VITE_VOICE=1 the mic only appears in mock mode, so no made-up words reach a real order.
export const VOICE_READY = MOCK || import.meta.env.VITE_VOICE === '1'
export const transcribe = (audio: Blob): Promise<string> =>
  MOCK
    ? mock().then((m) => m.transcribe(audio))
    : fetch(`${BASE}/api/voice/transcribe`, { method: 'POST', body: audio, headers: { 'Content-Type': audio.type || 'audio/webm', 'X-Agent-Key': getKeys().agentKey } })
        .then(async (r) => {
          if (!r.ok) throw new Error(`Couldn’t understand the recording (${r.status}). Try again, or type it.`)
          return ((await r.json()) as { text: string }).text
        })

// One box: the backend works out whether it's an order or a menu. requested_date only when the chef overrode it.
export const askAgent = (input: AskInput) =>
  MOCK ? mock().then((m) => m.ask(input)) : api<AskResponse>('/api/agent/ask', { ...post(input), headers: keyHeader('X-Agent-Key', getKeys().agentKey) }, 'agent')

// The same request, streamed (POST /api/agent/ask/stream, Server-Sent Events): `phase` {phase, text} as each step
// starts, then one `result` (the /ask body) or `error` {status, detail}. fetch + a stream reader, since EventSource
// can't POST. Falls back to plain /ask only when the stream never opened (the server started nothing); a stream that
// breaks midway is NOT retried, because the agent may already have ordered.
export type Phase = { phase: string; text: string }
export const DROPPED = 'The connection dropped before the answer came back. Check History before asking again, in case it was ordered.'
export async function askAgentStream(input: AskInput, onPhase: (p: Phase) => void): Promise<AskResponse> {
  if (MOCK) return mock().then((m) => m.askStream(input, onPhase))
  let res: Response
  try {
    res = await fetch(`${BASE}/api/agent/ask/stream`, {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...keyHeader('X-Agent-Key', getKeys().agentKey) },
    })
  } catch {
    return askAgent(input) // never reached the server
  }
  if (res.status === 404 || res.status === 405 || (res.ok && !res.body)) return askAgent(input) // no stream here
  if (!res.ok) throw await failure(res, 'agent')

  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value
      let end: number
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, end)
        buffer = buffer.slice(end + 2)
        let event = 'message'
        const data: string[] = []
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
        }
        if (!data.length) continue
        const body = JSON.parse(data.join('\n'))
        if (event === 'phase') onPhase(body as Phase)
        else if (event === 'result') return body as AskResponse
        else if (event === 'error') {
          const detail = typeof body.detail === 'string' ? body.detail : (body.detail?.error ?? 'unexpected error')
          throw failureFrom(Number(body.status) || 500, detail, 'agent')
        }
      }
    }
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new Error(DROPPED)
  } finally {
    reader.cancel().catch(() => {})
  }
  throw new Error(DROPPED)
}

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
// The rules' version travels as an ETag: read it with the rules, send it back as If-Match when saving (412 if someone
// saved in between). Cross-origin, the backend must list ETag in Access-Control-Expose-Headers, or this reads null
// and saves go without If-Match, as before.
export const getMandate = async (): Promise<{ mandate: Mandate | null; etag: string | null }> => {
  if (MOCK) return mock().then((m) => m.getMandate())
  const res = await request('/api/mandate', { headers: approver() }, 'approver')
  return { mandate: await json<Mandate | null>(res), etag: res.headers.get('ETag') }
}
export const compileRules = (text: string) =>
  MOCK ? mock().then((m) => m.compile(text)) : api<CompileResult>('/api/mandate/compile', { ...post({ text }), headers: approver() }, 'approver')
export const saveMandate = async (mandate: Mandate, confirm_large_change: boolean, etag: string | null): Promise<SaveResult & { etag: string | null }> => {
  if (MOCK) return mock().then((m) => m.saveMandate(mandate, etag))
  const res = await request(
    '/api/mandate',
    { method: 'PUT', body: JSON.stringify({ mandate, confirm_large_change }), headers: { ...approver(), ...(etag ? { 'If-Match': etag } : {}) } },
    'approver',
  )
  return { ...(await json<SaveResult>(res)), etag: res.headers.get('ETag') }
}

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
