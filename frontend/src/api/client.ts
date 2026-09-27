// A thin, typed wrapper around fetch() - one function per backend endpoint.
// Components never build URLs or headers themselves; they call these functions.

import { Capacitor } from '@capacitor/core'
import type {
  AuthResult, ChatHistoryItem, ChatReply, DailyStatus, Food, FoodLogEntry, FoodLogUpdate, Goal, Insight,
  MealSuggestion, Pace, PantryItem, PendingAction, Plan, Progress, RegisterData, User, UserUpdate, Week,
  Workout, WorkoutStats,
} from './types'

// Where the API lives:
//  - web (dev and production): the same origin, under /api (Vite proxies it in dev, see vite.config.ts)
//  - Android app: its pages load from inside the phone, so it must call the live server by full URL
const PRODUCTION_API = 'https://fitflow-rgtr.onrender.com/api'
const BASE = import.meta.env.VITE_API_URL ?? (Capacitor.isNativePlatform() ? PRODUCTION_API : '/api')
const TOKEN_KEY = 'fitflow.token'
export const LOGGED_OUT_EVENT = 'fitflow:logged-out'

// --- the login token (a JWT from /auth/login or /auth/register) ---
// Kept in localStorage so the user stays logged in across visits. Trade-off: any script running on
// the page could read it (XSS). The alternative, an httpOnly cookie, is safer but needs CSRF protection.

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null // storage can be blocked (private mode); the user then logs in each visit
  }
}

export function setToken(token: string | null) {
  try {
    if (token === null) localStorage.removeItem(TOKEN_KEY)
    else localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // ignore - worst case the user logs in again
  }
}

export function logout() {
  setToken(null)
  window.dispatchEvent(new Event(LOGGED_OUT_EVENT)) // App listens and shows the welcome screen
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
  if (status === 401) return 'צריך להתחבר מחדש'
  if (status === 404) return 'לא נמצא'
  if (status === 409) return 'הפעולה כבר לא אפשרית'
  if (status === 422) return 'חלק מהנתונים לא תקינים'
  if (status === 429) return 'עומס רגעי, נסה שוב בעוד דקה'
  if (status === 503) return 'השירות לא זמין כרגע'
  return 'משהו השתבש, נסה שוב'
}

/** A user-facing Hebrew message for any error thrown while calling the API. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.detail.includes('not configured')) {
    return 'המאמן עוד לא מחובר: צריך להגדיר מפתח GEMINI_API_KEY (חינמי) בקובץ .env בשרת.'
  }
  if (e instanceof ApiError && e.detail.startsWith('Daily chat limit')) {
    return 'הגעת למכסת ההודעות היומית של המאמן. נתראה מחר! בינתיים אפשר לרשום ידנית באימונים ובמה לאכול.'
  }
  if (e instanceof ApiError && e.detail.startsWith('The coach is')) {
    // The AI runs on a free tier: short overloads and per-minute limits are normal, not a bug.
    return 'המאמן עמוס כרגע, נסה שוב בעוד דקה.'
  }
  if (e instanceof ApiError) return e.message
  return 'אין חיבור לשרת, נסה שוב'  // fetch() itself failed: network down or server not running
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 401 && token) logout() // expired or invalid token -> back to login
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
const patch = <T>(path: string, body?: unknown) => request<T>('PATCH', path, body)
const del = (path: string) => request<void>('DELETE', path)

// --- endpoints ---

export const api = {
  register: (data: RegisterData) => post<AuthResult>('/auth/register', data),
  login: (email: string, password: string) => post<AuthResult>('/auth/login', { email, password }),
  me: () => get<User>('/me'),
  updateMe: (changes: UserUpdate) => patch<User>('/me', changes),
  planPreview: (goal: Goal, weightKg: number, targetKg: number, pace: Pace) =>
    get<Plan>(`/plan-preview?goal=${goal}&weight_kg=${weightKg}&target_weight_kg=${targetKg}&pace=${pace}`),

  today: () => get<DailyStatus>('/today'),
  deleteFood: (id: number) => del(`/log/food/${id}`),
  updateFood: (id: number, changes: FoodLogUpdate) => patch<FoodLogEntry>(`/log/food/${id}`, changes),
  logFood: (foodId: number, servings: number) => post('/log/food', { food_id: foodId, servings }),
  logWorkout: (activity: string, minutes: number) => post<Workout>('/log/workout', { activity, minutes }),
  deleteWorkout: (id: number) => del(`/log/workout/${id}`),
  updateWorkout: (id: number, changes: { activity?: string; minutes?: number }) =>
    patch<Workout>(`/log/workout/${id}`, changes),
  logWeight: (weightKg: number) => post('/log/weight', { weight_kg: weightKg }),
  importWorkouts: (workouts: { external_id: string; workout_type: string; start: string; minutes: number; kcal: number | null }[]) =>
    post<{ imported: number; skipped: number }>('/log/workouts/import', { workouts }),
  activities: () => get<Record<string, string>>('/log/activities'),

  searchFoods: (q: string) => get<Food[]>(`/foods?q=${encodeURIComponent(q)}`),
  pantry: () => get<PantryItem[]>('/pantry'),
  setPantryItem: (foodId: number, maxServings: number) => put(`/pantry/${foodId}`, { max_servings: maxServings }),
  removePantryItem: (foodId: number) => del(`/pantry/${foodId}`),

  // `exclude`: food-id lists of earlier suggestions, so "a different suggestion" finds a new combination.
  mealSuggestion: (exclude: number[][] = []) =>
    get<MealSuggestion>(
      `/coach/meal-suggestion?hour=${new Date().getHours()}` + exclude.map((ids) => `&exclude=${ids.join(',')}`).join(''),
    ),
  fitMeal: (foodIds: number[]) => post<MealSuggestion>('/coach/fit-meal', { food_ids: foodIds, hour: new Date().getHours() }),
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
