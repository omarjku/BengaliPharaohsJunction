import { ApiError, getKeys, MOCK } from './api'
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

export type CalendarSkipResponse = { weekday: string; date: string; skipped: boolean }
export type CalendarDeleteResponse = { weekday: Weekday; deleted: boolean }

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
      const body = (await response.json()) as { detail?: unknown; error?: unknown }
      const value = body.detail ?? body.error
      if (typeof value === 'string') detail = value
      else if (Array.isArray(value)) {
        const messages = value.map((item) => item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string' ? item.msg : null).filter(Boolean)
        if (messages.length) detail = messages.join('; ')
      } else if (value && typeof value === 'object') {
        if ('error' in value && typeof value.error === 'string') detail = value.error
        else if ('errors' in value && value.errors && typeof value.errors === 'object') {
          detail = Object.entries(value.errors as Record<string, unknown>)
            .map(([key, message]) => `${key}: ${String(message)}`)
            .join('; ')
        }
      }
    } catch {
      // Keep the status text when the backend did not return JSON.
    }
    if (response.status === 401 || response.status === 403)
      throw new ApiError(response.status, role === 'agent' ? `Enter a valid agent key in Keys. ${detail}` : `Approver key needed: enter it in Keys. ${detail}`)
    throw new ApiError(response.status, `Request failed (${response.status}): ${detail}`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const FULL_WEEKDAYS: Record<string, Weekday> = {
  monday: 'mon', tuesday: 'tue', wednesday: 'wed', thursday: 'thu', friday: 'fri', saturday: 'sat', sunday: 'sun',
}

function normaliseCalendar(response: CalendarResponse): CalendarResponse {
  return {
    ...response,
    days: response.days.map((day) => ({
      ...day,
      entries: day.entries.map((entry) => entry.kind === 'recurring_order'
        ? {
            ...entry,
            weekday: FULL_WEEKDAYS[entry.weekday] ?? entry.weekday,
            lines: entry.lines.map((line) => {
              const backendLine = line as CalendarLine & { text?: string; quantity?: number; unit?: string | null }
              return {
              name: backendLine.text ?? backendLine.name,
              quantity: backendLine.quantity ?? 1,
              unit: backendLine.unit ?? null,
              }
            }),
          }
        : entry),
    })),
  }
}

export function getCalendar(from: string, to: string): Promise<CalendarResponse> {
  if (MOCK) return mock().then((api) => api.calendar(from, to)).then(normaliseCalendar)
  const query = new URLSearchParams({ from, to })
  return requestJson<CalendarResponse>(`/api/calendar?${query}`, {}, 'agent').then(normaliseCalendar)
}

export function getWeeklyMenus(): Promise<WeeklyMenu[]> {
  if (MOCK)
    return mock().then((api) => api.weeklyMenus())
  return requestJson<WeeklyMenu[]>('/api/menus/weekly', {}, 'agent')
}

export function saveWeeklyMenu(weekday: Weekday, menu: WeeklyMenu): Promise<WeeklyMenu> {
  if (MOCK) return mock().then((api) => api.saveWeeklyMenu(weekday, menu))
  return requestJson<WeeklyMenu>(`/api/menus/weekly/${weekday}`, { method: 'PUT', body: JSON.stringify(menu) }, 'approver')
}

export function deleteWeeklyMenu(weekday: Weekday): Promise<CalendarDeleteResponse> {
  if (MOCK) return mock().then((api) => api.deleteWeeklyMenu(weekday))
  return requestJson<CalendarDeleteResponse>(`/api/menus/weekly/${weekday}`, { method: 'DELETE' }, 'approver')
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
