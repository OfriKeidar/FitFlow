// Hebrew display labels for values that the API sends as English identifiers.

import type { ActivityLevel, Frequency, Goal, WorkoutCategory } from './api/types'

export const GOAL_LABELS: Record<Goal, string> = {
  cut: 'חיטוב',
  bulk: 'מסה',
  recomp: 'ריקומפוזיציה',
  maintain: 'שמירה',
}

export const ACTIVITY_LEVEL_LABELS: Record<ActivityLevel, string> = {
  sedentary: 'יושבני',
  light: 'פעיל קלות',
  active: 'פעיל מאוד',
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

/** "2026-09-24" -> "יום חמישי" */
export function weekdayName(isoDay: string): string {
  return new Date(isoDay + 'T12:00:00').toLocaleDateString('he-IL', { weekday: 'long' })
}
