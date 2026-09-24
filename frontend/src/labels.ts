// Hebrew display labels for values that the API sends as English identifiers.

import type { ActivityLevel, Frequency, Goal, Pace, WorkoutCategory } from './api/types'
import type { IconName } from './components/Icon'

export const GOAL_LABELS: Record<Goal, string> = {
  cut: 'חיטוב',
  bulk: 'מסה',
  maintain: 'שמירה',
}

export const ACTIVITY_LEVELS: Record<ActivityLevel, { title: string; sub: string }> = {
  sedentary: { title: 'לא פעיל', sub: 'רוב היום בישיבה, למשל עבודה מול מחשב' },
  light: { title: 'פעיל קלות', sub: 'הרבה הליכה או עמידה במהלך היום' },
  active: { title: 'פעיל מאוד', sub: 'עבודה פיזית רוב היום' },
}

export const PACE_LABELS: Record<Pace, string> = {
  relaxed: 'רגוע',
  recommended: 'מומלץ',
  fast: 'מהיר',
}

export const FREQUENCY_LABELS: Record<Frequency, string> = {
  daily: 'כל יום',
  weekly: 'פעם בשבוע',
  monthly: 'פעם בחודש',
}

export const CATEGORY_LABELS: Record<WorkoutCategory, string> = {
  strength: 'כוח',
  cardio: 'אירובי',
  other: 'אחר',
}

export const ACTIVITY_NAMES: Record<string, string> = {
  strength_training: 'אימון כוח',
  crossfit: 'קרוספיט',
  walking: 'הליכה',
  brisk_walking: 'הליכה מהירה',
  running: 'ריצה',
  cycling: 'רכיבה',
  swimming: 'שחייה',
  hiit: 'HIIT',
  yoga: 'יוגה',
  pilates: 'פילאטיס',
  football: 'כדורגל',
  basketball: 'כדורסל',
}

export const activityName = (id: string) => ACTIVITY_NAMES[id] ?? id

/** A personal greeting that matches the time of day. */
export function greeting(hour = new Date().getHours()): { text: string; icon: IconName } {
  if (hour >= 5 && hour < 12) return { text: 'בוקר טוב', icon: 'sunrise' }
  if (hour >= 12 && hour < 17) return { text: 'צהריים טובים', icon: 'sun' }
  if (hour >= 17 && hour < 21) return { text: 'ערב טוב', icon: 'sunset' }
  return { text: 'לילה טוב', icon: 'moon' }
}

/** "2026-12-15" -> "15 בדצמבר" */
export function formatDate(isoDay: string): string {
  return new Date(isoDay + 'T12:00:00').toLocaleDateString('he-IL', { day: 'numeric', month: 'long' })
}

/** "2026-09-24" -> "יום חמישי" */
export function weekdayName(isoDay: string): string {
  return new Date(isoDay + 'T12:00:00').toLocaleDateString('he-IL', { weekday: 'long' })
}
