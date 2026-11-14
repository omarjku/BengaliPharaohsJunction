import { getKeys, MOCK } from './api'
import type { AskResponse, MenuRun, OrderStatus } from './types'

export type Weekday = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'

export type CalendarLine = { name: string; quantity: number; unit: string | null }

type DeliveryEntryBase = {
  order_id: string
  title: string
  lines: CalendarLine[]
  total_cents: number
  status: OrderStatus
}

export type DeliveryConfirmedEntry = DeliveryEntryBase & { kind: 'delivery_confirmed' }
export type DeliveryPendingEntry = DeliveryEntryBase & { kind: 'delivery_pending'; reason: string }
export type RecurringOrderEntry = {
  kind: 'recurring_order'
  weekday: Weekday
  lines: CalendarLine[]
  source: string
  placed: boolean
}
export type WeeklyMenuEntry = {
  kind: 'weekly_menu'
  name: string
  dishes: { name: string; has_recipe: boolean }[]
  covers?: number
}
export type GuestsExpectedEntry = { kind: 'guests_expected'; value: number; simulated: boolean }

export type CalendarEntry =
  | DeliveryConfirmedEntry
  | DeliveryPendingEntry
  | RecurringOrderEntry
  | WeeklyMenuEntry
  | GuestsExpectedEntry

export type CalendarDay = {
  date: string
  today: boolean
  cutoff?: { closing_time: string; passed: boolean }
  entries: CalendarEntry[]
}

export type CalendarResponse = {
  days: CalendarDay[]
  legend: Record<string, string>
}

export type WeeklyMenuDish = {
  name: string
  recipe?: string
  per_cover?: { ingredient: string; amount: number; unit: string }[]
}

export type WeeklyMenu = {
  weekday: Weekday
  name: string
  dishes: WeeklyMenuDish[]
  covers?: number
  active: boolean
}

export type CalendarSkipResponse = { skipped: boolean }

const BASE = import.meta.env.VITE_API_URL ?? ''

type AuthRole = 'agent' | 'approver'

const mock = () => import('./mock').then((module) => module.mockApi)

function authHeaders(role: AuthRole): HeadersInit {
  return role === 'agent'
    ? { 'X-Agent-Key': getKeys().agentKey }
    : { 'X-Approver-Key': getKeys().approverKey }
}

async function requestJson<T>(path: string, init: RequestInit, role: AuthRole): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...authHeaders(role), ...init.headers },
    })
  } catch {
    throw new Error("Can't reach the backend. Is it running?")
  }
  if (!response.ok) {
    let detail = response.statusText || 'unexpected response'
    try {
      const body = (await response.json()) as { detail?: string; error?: string }
      detail = body.detail ?? body.error ?? detail
    } catch {
      // Keep the status text when the backend did not return JSON.
    }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function requestVoid(path: string, init: RequestInit, role: AuthRole): Promise<void> {
  await requestJson<unknown>(path, init, role)
}

export function getCalendar(from: string, to: string): Promise<CalendarResponse> {
  if (MOCK) return mock().then((api) => api.calendar(from, to))
  const query = new URLSearchParams({ from, to })
  return requestJson<CalendarResponse>(`/api/calendar?${query}`, {}, 'agent')
}

export function getWeeklyMenus(): Promise<WeeklyMenu[]> {
  if (MOCK)
    return mock().then((api) => api.weeklyMenus())
  return requestJson<WeeklyMenu[] | { menus: WeeklyMenu[] }>('/api/menus/weekly', {}, 'agent').then((result) =>
    Array.isArray(result) ? result : result.menus,
  )
}

export function saveWeeklyMenu(weekday: Weekday, menu: WeeklyMenu): Promise<WeeklyMenu> {
  if (MOCK) return mock().then((api) => api.saveWeeklyMenu(weekday, menu))
  return requestJson<WeeklyMenu | undefined>(`/api/menus/weekly/${weekday}`, { method: 'PUT', body: JSON.stringify(menu) }, 'approver').then((result) => result ?? menu)
}

export function deleteWeeklyMenu(weekday: Weekday): Promise<void> {
  if (MOCK) return mock().then((api) => api.deleteWeeklyMenu(weekday))
  return requestVoid(`/api/menus/weekly/${weekday}`, { method: 'DELETE' }, 'approver')
}

export function planWeeklyMenu(weekday: Weekday, date: string): Promise<MenuRun> {
  if (MOCK) return mock().then((api) => api.planWeeklyMenu(weekday, date))
  return requestJson<MenuRun>(`/api/menus/weekly/${weekday}/plan?date=${encodeURIComponent(date)}`, {}, 'agent')
}

export function placeRecurring(weekday: Weekday, date: string): Promise<AskResponse> {
  if (MOCK) return mock().then((api) => api.placeRecurring(weekday, date))
  return requestJson<AskResponse>(`/api/calendar/recurring/${weekday}/place?date=${encodeURIComponent(date)}`, { method: 'POST' }, 'agent')
}

export function skipRecurring(weekday: Weekday, date: string): Promise<CalendarSkipResponse> {
  if (MOCK) return mock().then((api) => api.skipRecurring(weekday, date))
  return requestJson<CalendarSkipResponse>(`/api/calendar/recurring/${weekday}/skip?date=${encodeURIComponent(date)}`, { method: 'POST' }, 'approver')
}
