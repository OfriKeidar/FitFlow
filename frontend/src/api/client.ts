// A thin, typed wrapper around fetch() - one function per backend endpoint.
// Components never build URLs or headers themselves; they call these functions.

import type {
  ChatHistoryItem, ChatReply, DailyStatus, Food, Goal, Insight, MealSuggestion, PantryItem, Pace,
  PendingAction, Plan, Progress, User, UserCreate, Week, Workout, WorkoutStats,
} from './types'

const BASE = '/api' // proxied to FastAPI by Vite (see vite.config.ts)
const USER_KEY = 'fitflow.userId'

// --- the logged-in user ---
// TODO(auth): the backend identifies users by an X-User-Id header for now. Replace with JWT.

export function getUserId(): string | null {
  try {
    return localStorage.getItem(USER_KEY)
  } catch {
    return null // storage can be blocked (private mode); the app then shows onboarding
  }
}

export function setUserId(id: number | null) {
  try {
    if (id === null) localStorage.removeItem(USER_KEY)
    else localStorage.setItem(USER_KEY, String(id))
  } catch {
    // ignore - worst case the user onboards again
  }
}

// --- core request helper ---

export class ApiError extends Error {
  status: number
  detail: string // the server's own (English) message, useful for debugging
  constructor(status: number, detail: string) {
    super(userMessage(status))
    this.status = status
    this.detail = detail
  }
}

/** What the user sees for each kind of failure (server messages are English and technical). */
function userMessage(status: number): string {
  if (status === 404) return 'לא נמצא'
  if (status === 409) return 'הפעולה כבר לא אפשרית'
  if (status === 422) return 'חלק מהנתונים לא תקינים'
  if (status === 429) return 'עומס רגעי, נסה שוב בעוד דקה'
  if (status === 503) return 'השירות לא זמין כרגע'
  return 'משהו השתבש, נסה שוב'
}

/** A user-facing Hebrew message for any error thrown while calling the API. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.detail.includes('ANTHROPIC_API_KEY')) {
    return 'המאמן עוד לא מחובר: צריך להגדיר מפתח ANTHROPIC_API_KEY בשרת.'
  }
  if (e instanceof ApiError) return e.message
  return 'אין חיבור לשרת, נסה שוב'  // fetch() itself failed: network down or server not running
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const userId = getUserId()
  if (userId) headers['X-User-Id'] = userId
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    // FastAPI errors look like {"detail": "..."}; fall back to the status text.
    const data = await response.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

const get = <T>(path: string) => request<T>('GET', path)
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body)
const put = <T>(path: string, body?: unknown) => request<T>('PUT', path, body)
const del = (path: string) => request<void>('DELETE', path)

// --- endpoints ---

export const api = {
  createUser: (data: UserCreate) => post<User>('/users', data),
  me: () => get<User>('/me'),
  planPreview: (goal: Goal, weightKg: number, targetKg: number, pace: Pace) =>
    get<Plan>(`/plan-preview?goal=${goal}&weight_kg=${weightKg}&target_weight_kg=${targetKg}&pace=${pace}`),

  today: () => get<DailyStatus>('/today'),
  deleteFood: (id: number) => del(`/log/food/${id}`),
  logFood: (foodId: number, servings: number) => post('/log/food', { food_id: foodId, servings }),
  logWorkout: (activity: string, minutes: number) => post<Workout>('/log/workout', { activity, minutes }),
  deleteWorkout: (id: number) => del(`/log/workout/${id}`),
  logWeight: (weightKg: number) => post('/log/weight', { weight_kg: weightKg }),
  activities: () => get<Record<string, string>>('/log/activities'),

  searchFoods: (q: string) => get<Food[]>(`/foods?q=${encodeURIComponent(q)}`),
  pantry: () => get<PantryItem[]>('/pantry'),
  setPantryItem: (foodId: number, maxServings: number) => put(`/pantry/${foodId}`, { max_servings: maxServings }),
  removePantryItem: (foodId: number) => del(`/pantry/${foodId}`),

  mealSuggestion: () => get<MealSuggestion>(`/coach/meal-suggestion?hour=${new Date().getHours()}`),
  insights: () => get<Insight[]>('/coach/insights'),
  week: () => get<Week>('/workouts/week'),
  workoutStats: () => get<WorkoutStats>('/workouts/stats'),
  progress: () => get<Progress>('/progress'),

  chat: (message: string) => post<ChatReply>('/chat', { message, hour: new Date().getHours() }),
  chatHistory: () => get<ChatHistoryItem[]>('/chat/history'),
  pendingActions: () => get<PendingAction[]>('/chat/actions'),
  confirmAction: (id: number) => post<PendingAction>(`/chat/actions/${id}/confirm`),
  rejectAction: (id: number) => post<PendingAction>(`/chat/actions/${id}/reject`),
}
