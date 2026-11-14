import { ApiError, getKeys, MOCK } from './api'
import type { AnswerValue, Saved, StandingOrderAnswer } from './onboardingApi'
import type { LiveEvent, LiveSocket } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

export type Weekday = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'
export const WEEKDAYS: Weekday[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export type StandingOrderLine = {
  text: string
  product_id?: string
  quantity?: number
  unit?: string
}

export type StandingOrder = {
  weekday: Weekday
  lines: StandingOrderLine[]
  source: string
}

export type KitchenHistory = {
  basis: 'example' | 'own' | 'mixed'
  covers_by_weekday: Record<Weekday, number | null>
  covers_source: Record<Weekday, 'example' | 'own'>
  standing_orders: StandingOrder[]
  usual_products: { product_id: string; name: string; source: string }[]
  labels: { example: string }
}

export type KitchenProfile = {
  buyer_id: string
  dietary: { tag: string; label: string; because: string }[]
  allergens: string[]
  delivery_days: string[]
  usual_product_ids: string[]
  standing_orders: { weekday: string; lines: StandingOrderLine[]; key?: string; source?: string; source_detail?: string }[]
  notes: { text: string; source: string; source_detail: string }[]
  usual_products: { text: string; source: string; source_detail: string }[]
  onboarding_facts: { key: string; value: unknown; source: string; source_detail: string }[]
  memories: unknown[]
  suggested_questions: string[]
  recent_orders: unknown[]
  onboarded: boolean
}

export type InterviewTopic =
  | 'kitchen'
  | 'delivery_days'
  | 'standing_orders'
  | 'dietary_allergens'
  | 'usual_products'
  | 'budget'
  | 'anything_else'

export type InterviewAnswer = { topic: InterviewTopic; text: string }
export type InterviewValue = AnswerValue | StandingOrderAnswer[]
export type InterviewPreview = {
  stored: false
  proposed: { id: string; question: string; value: InterviewValue }[]
  unclear: string[]
  hints: string[]
}
export type InterviewNextResponse =
  | { done: false; topic: InterviewTopic; question: string }
  | { done: true; preview: InterviewPreview }

export type StandingOrderUpdate = KitchenProfile
export type KitchenLiveEvent = LiveEvent | { type: 'interview_preview'; preview: InterviewPreview }
export type KitchenLiveHandlers = { onEvent: (event: KitchenLiveEvent) => void; onClose: () => void }

type AuthHeader = 'X-Agent-Key' | 'X-Approver-Key'

function keyFor(header: AuthHeader): string {
  return header === 'X-Agent-Key' ? getKeys().agentKey : getKeys().approverKey
}

async function detail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    const value = body.detail
    if (typeof value === 'string') return value
    if (Array.isArray(value)) {
      const messages = value.map((item) => item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string' ? item.msg : null).filter(Boolean)
      if (messages.length) return messages.join('; ')
    }
    if (value && typeof value === 'object') {
      if ('error' in value && typeof value.error === 'string') return value.error
      if ('errors' in value && value.errors && typeof value.errors === 'object') {
        return Object.entries(value.errors as Record<string, unknown>)
          .map(([key, message]) => `${key}: ${String(message)}`)
          .join('; ')
      }
    }
  } catch {
    // The status text is the only useful detail when the server did not return JSON.
  }
  return response.statusText || 'unexpected error'
}

async function fetchJson<T>(path: string, init: RequestInit, header: AuthHeader): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(keyFor(header) ? { [header]: keyFor(header) } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new Error("Can't reach the backend. Is it running?")
  }
  if (!response.ok) {
    const message = await detail(response)
    if (response.status === 401 || response.status === 403)
      throw new ApiError(response.status, header === 'X-Agent-Key' ? `Enter a valid agent key in Keys. ${message}` : `Approver key needed: enter it in Keys. ${message}`)
    throw new ApiError(response.status, `Request failed (${response.status}): ${message}`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const getKitchenHistory = (): Promise<KitchenHistory> =>
  MOCK
    ? import('./mock').then((m) => m.mockApi.kitchenHistory())
    : fetchJson<KitchenHistory>('/api/kitchen/history', { method: 'GET' }, 'X-Agent-Key')

export const saveKitchenCovers = (covers: Record<Weekday, number>): Promise<KitchenHistory> =>
  MOCK
    ? import('./mock').then((m) => m.mockApi.saveKitchenCovers(covers))
    : fetchJson<KitchenHistory>('/api/kitchen/history/covers', { method: 'PUT', body: JSON.stringify(covers) }, 'X-Approver-Key')

export const clearExampleHistory = (): Promise<KitchenHistory> =>
  MOCK
    ? import('./mock').then((m) => m.mockApi.clearExampleHistory())
    : fetchJson<KitchenHistory>('/api/kitchen/history/clear-example', { method: 'POST' }, 'X-Approver-Key')

export const saveStandingOrder = (weekday: Weekday, lines: StandingOrderLine[]): Promise<StandingOrderUpdate> =>
  MOCK
    ? import('./mock').then((m) => m.mockApi.saveStandingOrder(weekday, lines))
    : fetchJson<StandingOrderUpdate>(`/api/profile/standing-orders/${weekday}`, { method: 'PUT', body: JSON.stringify({ lines }) }, 'X-Approver-Key')

export const deleteStandingOrder = (weekday: Weekday): Promise<StandingOrderUpdate> =>
  MOCK
    ? import('./mock').then((m) => m.mockApi.deleteStandingOrder(weekday))
    : fetchJson<StandingOrderUpdate>(`/api/profile/standing-orders/${weekday}`, { method: 'DELETE' }, 'X-Approver-Key')

export const getInterviewNext = (answers: InterviewAnswer[]): Promise<InterviewNextResponse> =>
  MOCK
    ? import('./mock').then((m) => m.interviewNext(answers))
    : fetchJson<InterviewNextResponse>('/api/profile/interview/next', { method: 'POST', body: JSON.stringify({ answers }) }, 'X-Agent-Key')

export const confirmInterview = (answers: Record<string, InterviewValue>): Promise<Saved> =>
  MOCK
    ? import('./mock').then((m) => m.confirmInterview(answers))
    : fetchJson<Saved>('/api/profile/onboarding', { method: 'POST', body: JSON.stringify({ answers, confirm: true }) }, 'X-Approver-Key')

export function openInterviewLive(handlers: KitchenLiveHandlers): Promise<Pick<LiveSocket, 'send' | 'close'>> {
  if (MOCK) return import('./mock').then((m) => m.mockApi.live(handlers, 'interview'))
  const base = BASE || window.location.origin
  const ws = new WebSocket(`${base.replace(/^http/, 'ws')}/api/live`)
  ws.onmessage = (message) => {
    try {
      handlers.onEvent(JSON.parse(message.data as string) as KitchenLiveEvent)
    } catch {
      // not JSON: ignore it
    }
  }
  ws.onclose = () => handlers.onClose()
  return new Promise((resolve, reject) => {
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', agent_key: getKeys().agentKey, mode: 'interview' }))
      resolve({ send: (message) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(message)), close: () => ws.close() })
    }
    ws.onerror = () => reject(new Error("Can't reach the live voice service."))
  })
}
