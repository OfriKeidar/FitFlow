// Hebrew display labels for values that the API sends as English identifiers.

import type { ActivityLevel, Experience, Frequency, Goal, Pace, WorkoutCategory } from './api/types'
import type { IconName } from './components/Icon'

export const GOAL_LABELS: Record<Goal, string> = {
  cut: 'חיטוב',
  bulk: 'מסה',
  maintain: 'שמירה',
}

// What each goal means, shown under "מה זה אומר?" when choosing it - users who understand why the pace is
// moderate and protein is high make better choices (and trust the targets more).
export const GOAL_EXPLANATIONS: Record<Goal, { aim: string; points: { icon: IconName; text: string }[] }> = {
  cut: {
    aim: 'המטרה: להוריד שומן ולשמור על השריר.',
    points: [
      { icon: 'flame', text: 'אוכלים קצת פחות ממה שהגוף שורף (גרעון), והגוף משלים את החסר משומן.' },
      { icon: 'scale', text: 'גרעון גדול מדי או מעט חלבון גורמים לגוף לפרק גם שריר.' },
      { icon: 'barbell', text: 'לכן: קצב מתון, הרבה חלבון והמשך אימוני כוח, כדי שמה שיורד יהיה בעיקר שומן.' },
    ],
  },
  bulk: {
    aim: 'המטרה: לבנות שריר.',
    points: [
      { icon: 'kitchen', text: 'אוכלים קצת יותר ממה שהגוף שורף (עודף), כדי שיהיו לגוף חומרי בניין ואנרגיה לאימונים.' },
      { icon: 'clock', text: 'הגוף בונה שריר לאט, ומה שנאכל מעבר לזה נאגר כשומן.' },
      { icon: 'barbell', text: 'לכן: עודף קטן ומבוקר. קצת שומן הוא מחיר מקובל, ומורידים אותו אחר כך בחיטוב.' },
    ],
  },
  maintain: {
    aim: 'המטרה: לשמור על המשקל.',
    points: [
      { icon: 'equal', text: 'אוכלים בערך כמו שהגוף שורף.' },
      { icon: 'arrows', text: 'מתאים בין תקופות של חיטוב ומסה, או כשרוצים להתחזק בלי לשנות משקל.' },
    ],
  },
}

export const ACTIVITY_LEVELS: Record<ActivityLevel, { title: string; sub: string }> = {
  sedentary: { title: 'לא פעיל', sub: 'רוב היום בישיבה, למשל עבודה מול מחשב' },
  light: { title: 'פעיל קלות', sub: 'הרבה הליכה או עמידה במהלך היום' },
  active: { title: 'פעיל מאוד', sub: 'עבודה פיזית רוב היום' },
}

export const ACTIVITY_ICONS: Record<ActivityLevel, IconName> = { sedentary: 'user', light: 'run', active: 'barbell' }

export const PACE_LABELS: Record<Pace, string> = {
  relaxed: 'רגוע',
  recommended: 'מומלץ',
  fast: 'מהיר',
}

// Training experience sets how fast a bulk can go: beginners build muscle fastest.
export const EXPERIENCE_LABELS: Record<Experience, { title: string; sub: string }> = {
  beginner: { title: 'מתחיל', sub: 'פחות משנה של אימוני כוח' },
  intermediate: { title: 'בינוני', sub: 'שנה עד 3 שנים' },
  advanced: { title: 'מתקדם', sub: 'יותר מ־3 שנים' },
}

export const WORKOUT_GOAL_OPTIONS = [1, 2, 3, 4, 5, 6]

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
  other: 'אימון אחר',
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

/** "2026-09-27" -> "יום ראשון 27/09/2026" */
export function fullDate(isoDay: string): string {
  const [year, month, day] = isoDay.split('-')
  return `${weekdayName(isoDay)} ${day}/${month}/${year}`
}
