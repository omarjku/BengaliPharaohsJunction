// Onboarding: the first-run questions about the kitchen (GET/POST /api/profile/onboarding). Answers are guidance for
// the agent, never rules: the backend refuses nothing here into the mandate. Own file so api.ts stays untouched.
import { useCallback, useEffect, useState } from 'react'
import { MOCK, getKeys } from './api'

const BASE = import.meta.env.VITE_API_URL ?? ''

export type QuestionInput = 'text' | 'choice' | 'multi'
export type AnswerValue = string | number | string[] | { city: string; region: string | null }
export type Question = { id: string; question: string; input: QuestionInput; options?: string[]; answer?: AnswerValue }
export type Onboarding = { onboarded: boolean; questions: Question[] }
export type Preview = { stored: false; proposed: { id: string; question: string; value: AnswerValue }[]; unclear: string[]; hints: string[] }
export type Saved = { stored: true; saved: string[]; hints: string[]; onboarding: Onboarding }

// A failed save keeps the backend's per-question reasons ({errors: {id: reason}}) so each can sit under its field.
export class OnboardingError extends Error {
  status: number
  errors: Record<string, string>
  constructor(status: number, message: string, errors: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

async function call<T>(path: string, init: RequestInit, header: 'X-Agent-Key' | 'X-Approver-Key'): Promise<T> {
  const key = header === 'X-Agent-Key' ? getKeys().agentKey : getKeys().approverKey
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(key ? { [header]: key } : {}) } })
  } catch {
    throw new OnboardingError(0, "Can't reach the backend.")
  }
  const body = (await res.json().catch(() => ({}))) as { detail?: unknown }
  if (res.ok) return body as T
  const d = body.detail
  if (d && typeof d === 'object' && 'errors' in d) throw new OnboardingError(res.status, 'Some answers need a fix.', (d as { errors: Record<string, string> }).errors)
  throw new OnboardingError(res.status, typeof d === 'string' ? d : `Request failed (${res.status}).`)
}

export const getOnboarding = (): Promise<Onboarding> =>
  MOCK ? Promise.resolve(mockOnboarding()) : call<Onboarding>('/api/profile/onboarding', { method: 'GET' }, 'X-Agent-Key')

export const previewAbout = (about: string): Promise<Preview> =>
  MOCK
    ? new Promise((ok) => setTimeout(() => ok(MOCK_PREVIEW), 600))
    : call<Preview>('/api/profile/onboarding', { method: 'POST', body: JSON.stringify({ about }) }, 'X-Approver-Key')

export const saveAnswers = (answers: Record<string, AnswerValue>): Promise<Saved> => {
  if (MOCK) {
    mockState.answers = { ...mockState.answers, ...answers }
    return Promise.resolve({ stored: true, saved: Object.keys(answers), hints: [], onboarding: mockOnboarding() })
  }
  return call<Saved>('/api/profile/onboarding', { method: 'POST', body: JSON.stringify({ answers, confirm: true }) }, 'X-Approver-Key')
}

// Room 4 mounts <Onboarding> when this says false. null = unknown (no agent key yet, or the backend is unreachable):
// don't show onboarding on a guess.
export function useOnboarded(): { onboarded: boolean | null; refresh: () => void } {
  const [onboarded, setOnboarded] = useState<boolean | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!MOCK && !getKeys().agentKey) return
    let live = true
    getOnboarding()
      .then((o) => live && setOnboarded(o.onboarded))
      .catch(() => live && setOnboarded(null))
    return () => {
      live = false
    }
  }, [tick])
  return { onboarded, refresh: useCallback(() => setTick((n) => n + 1), []) }
}

// --- mock mode (?mock=1 on the dev server): the backend's real question list, and the reading Gemini gave for the
// sample sentence in the backend's real run (docs: room2-onboarding). Nothing here reaches a build without VITE_MOCK.
const mockState: { answers: Record<string, AnswerValue> } = { answers: {} }
const MOCK_QUESTIONS: Question[] = [
  { id: 'business_type', question: 'What kind of business do you run?', input: 'text' },
  { id: 'delivery_days', question: 'Which weekdays can you receive deliveries?', input: 'multi',
    options: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] },
  { id: 'allergens', question: 'Which allergens must we always avoid?', input: 'multi',
    options: ['celery', 'crustaceans', 'egg', 'fish', 'gluten (cereals)', 'lupin', 'milk', 'molluscs', 'mustard', 'peanuts', 'sesame', 'soy', 'sulphites', 'tree nuts', 'wheat'] },
  { id: 'spend_comfort', question: 'What order total are you comfortable with on your own?', input: 'text' },
  { id: 'local_preference', question: 'Do you prefer Finnish / local products?', input: 'choice', options: ['yes', 'no', 'no preference'] },
  { id: 'location', question: 'Where is your kitchen?', input: 'text' },
  { id: 'spare_level', question: 'How much spare do you want for kitchen loss?', input: 'choice', options: ['none', 'low', 'normal', 'high'] },
  { id: 'dietary', question: 'Which diets does your whole kitchen always follow?', input: 'multi',
    options: ['lactose_free', 'gluten_free', 'vegan', 'vegetarian', 'milk_free', 'egg_free', 'nut_free', 'peanut_free', 'soy_free', 'fish_free'] },
  { id: 'cuisine', question: 'What do you cook, and how do you serve it?', input: 'text' },
  { id: 'staples', question: 'What do you always keep in stock?', input: 'multi' },
]
const mockOnboarding = (): Onboarding => ({
  onboarded: Object.keys(mockState.answers).length > 0,
  questions: MOCK_QUESTIONS.map((q) => (q.id in mockState.answers ? { ...q, answer: mockState.answers[q.id] } : q)),
})
const MOCK_PREVIEW: Preview = {
  stored: false,
  proposed: [
    { id: 'business_type', question: 'What kind of business do you run?', value: '60-seat bistro' },
    { id: 'delivery_days', question: 'Which weekdays can you receive deliveries?', value: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'] },
    { id: 'dietary', question: 'Which diets does your whole kitchen always follow?', value: ['gluten_free'] },
    { id: 'local_preference', question: 'Do you prefer Finnish / local products?', value: 'yes' },
    { id: 'location', question: 'Where is your kitchen?', value: { city: 'Helsinki', region: null } },
    { id: 'spare_level', question: 'How much spare do you want for kitchen loss?', value: 'high' },
  ],
  unclear: [],
  hints: [],
}
