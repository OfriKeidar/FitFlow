import { useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { Week, WorkoutCategory, WorkoutStats } from '../api/types'
import { Icon, type IconName } from '../components/Icon'
import { useApi } from '../hooks/useApi'
import { ACTIVITY_NAMES, CATEGORY_LABELS, activityName } from '../labels'
import { useUser } from '../user'
import { isNativeApp, openHealthSettings, syncWorkouts, type SyncResult } from '../health'

const CATEGORY_STYLE: Record<WorkoutCategory, { icon: IconName; color: string }> = {
  strength: { icon: 'barbell', color: 'var(--strength)' },
  cardio: { icon: 'run', color: 'var(--cardio)' },
  other: { icon: 'ball', color: 'var(--other)' },
}
const DAY_LETTERS = ['א\'', 'ב\'', 'ג\'', 'ד\'', 'ה\'', 'ו\'', 'ש\'']

export function Workouts() {
  const week = useApi(api.week)
  const stats = useApi(api.workoutStats)
  const insights = useApi(api.insights)

  return (
    <>
      <div className="page-header">
        <h1>אימונים</h1>
        {week.data && (
          <span className="muted">
            השבוע · {total(week.data)} מתוך יעד {week.data.goal}
          </span>
        )}
      </div>

      {isNativeApp() && <HealthSyncCard onSynced={() => { week.reload(); stats.reload(); insights.reload() }} />}
      {week.data ? <WeekSummary week={week.data} /> : <div className="skeleton" style={{ height: 200 }} />}
      {stats.data && <StatsGrid stats={stats.data} goal={week.data?.goal ?? 0} />}
      <LogWorkout onLogged={() => { week.reload(); stats.reload(); insights.reload() }} />

      <h2>תובנות</h2>
      {insights.data?.length === 0 && (
        <p className="muted">עוד אין מספיק נתונים לתובנות. אחרי כמה שבועות של רישום, יופיעו כאן דפוסים מעניינים.</p>
      )}
      {insights.data?.map((i) => (
        <div key={i.kind} className="card row fade-in" style={{ justifyContent: 'flex-start' }}>
          <span style={{ color: 'var(--fat)' }}><Icon name={i.kind === 'workout_streak' ? 'flame' : 'bulb'} /></span>
          <span>{i.message}</span>
        </div>
      ))}
    </>
  )
}

function lastWorkoutText(days: number | null): string {
  if (days === null) return 'עוד לא'
  if (days === 0) return 'היום'
  if (days === 1) return 'אתמול'
  return `לפני ${days} ימים`
}

function StatsGrid({ stats, goal }: { stats: WorkoutStats; goal: number }) {
  const items: { icon: IconName; color: string; label: string; value: string }[] = [
    { icon: 'clock', color: 'var(--carbs)', label: 'אימון אחרון', value: lastWorkoutText(stats.days_since_last) },
    { icon: 'flame', color: '#D85A30', label: 'שבועות ברצף ביעד', value: `${stats.current_week_streak}` },
    { icon: 'trophy', color: 'var(--fat)', label: 'שיא שבועות ברצף', value: `${stats.best_week_streak}` },
    { icon: 'calendar', color: 'var(--accent)', label: 'החודש', value: `${stats.this_month} אימונים` },
    { icon: 'run', color: 'var(--cardio)', label: 'דקות השבוע', value: `${Math.round(stats.minutes_this_week)}` },
    { icon: 'heart', color: 'var(--danger)', label: 'האהוב עליך', value: stats.favorite_activity ? activityName(stats.favorite_activity) : '—' },
  ]
  return (
    <div className="stack" style={{ gap: 6 }}>
    <div className="grid-2">
      {items.map((item) => (
        <div key={item.label} className="stat-tile">
          <span className="stat-icon" style={{ color: item.color }}><Icon name={item.icon} size={18} /></span>
          <span>
            <div className="muted" style={{ fontSize: 12 }}>{item.label}</div>
            <div className="stat-value">{item.value}</div>
          </span>
        </div>
      ))}
    </div>
    <p className="muted" style={{ fontSize: 12 }}>
      "שבוע ביעד" הוא שבוע עם לפחות {goal} אימונים (היעד השבועי שלך). הרצף סופר שבועות כאלה ברציפות.
    </p>
    </div>
  )
}

/** Android app only: pull workouts from Samsung Health (via Health Connect). */
function HealthSyncCard({ onSynced }: { onSynced: () => void }) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function sync() {
    setBusy(true)
    setError(null)
    try {
      const r = await syncWorkouts()
      setResult(r)
      if (r.status === 'ok' && r.imported > 0) onSynced()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card stack">
      <div className="row">
        <h2 className="row" style={{ gap: 6 }}><Icon name="heart" /> Samsung Health</h2>
        <button className="btn small" disabled={busy} onClick={sync}>
          <Icon name="refresh" size={14} /> {busy ? 'מסנכרן…' : 'סנכרון'}
        </button>
      </div>
      <p className="muted" style={{ fontSize: 12 }}>
        אימונים מ־Samsung Health (דרך Health Connect) נכנסים לכאן אוטומטית בכל פתיחה של האפליקציה.
      </p>
      {result?.status === 'ok' && (
        <p className="pop" style={{ color: 'var(--accent)' }}>
          <Icon name="check" size={16} /> {result.imported > 0 ? `יובאו ${result.imported} אימונים חדשים` : 'הכל מעודכן, אין אימונים חדשים'}
        </p>
      )}
      {result?.status === 'unavailable' && (
        <p className="error-text">Health Connect לא זמין בטלפון הזה. אפשר להתקין אותו מ־Google Play.</p>
      )}
      {result?.status === 'denied' && (
        <p className="error-text">
          לא ניתנה הרשאה לקרוא אימונים. <button className="link-button" onClick={openHealthSettings}>פתיחת הגדרות Health Connect</button>
        </p>
      )}
      {error && <p className="error-text">{error}</p>}
    </div>
  )
}

const total = (week: Week) => Object.values(week.counts).reduce((a, b) => a + b, 0)

function WeekSummary({ week }: { week: Week }) {
  // Minutes trained per day of the week (Sunday first), and that day's main category for the color.
  const start = new Date(week.week_start + 'T12:00:00')
  const days = DAY_LETTERS.map((letter, i) => {
    const day = new Date(start)
    day.setDate(start.getDate() + i)
    const iso = day.toISOString().slice(0, 10)
    const workouts = week.workouts.filter((w) => w.day === iso)
    return { letter, minutes: workouts.reduce((a, w) => a + w.minutes, 0), category: workouts[0]?.category }
  })
  const maxMinutes = Math.max(60, ...days.map((d) => d.minutes))
  const goalReached = total(week) >= week.goal
  const user = useUser()

  return (
    <div className="card stack">
      <div className="grid-3" style={{ textAlign: 'center' }}>
        {(Object.keys(CATEGORY_STYLE) as WorkoutCategory[]).map((c) => (
          <div key={c} className="tile">
            <span style={{ color: CATEGORY_STYLE[c].color }}><Icon name={CATEGORY_STYLE[c].icon} /></span>
            <div style={{ fontSize: 22, fontWeight: 500 }}>{week.counts[c]}</div>
            <div className="muted">{CATEGORY_LABELS[c]}</div>
          </div>
        ))}
      </div>
      <div className="row" style={{ alignItems: 'flex-end', height: 80 }} role="img" aria-label="דקות אימון לפי ימים">
        {days.map((d) => (
          <div key={d.letter} style={{ flex: 1, textAlign: 'center' }}>
            <div
              style={{
                height: d.minutes ? Math.max(8, (d.minutes / maxMinutes) * 60) : 4,
                background: d.category ? CATEGORY_STYLE[d.category].color : 'var(--surface-2)',
                borderRadius: 4, margin: '0 3px', transition: 'height 0.5s',
              }}
            />
            <div className="muted" style={{ fontSize: 11 }}>{d.letter}</div>
          </div>
        ))}
      </div>
      {goalReached && <p className="banner accent pop"><Icon name="trophy" /> כל הכבוד {user.name}, הגעת ליעד האימונים השבועי!</p>}
    </div>
  )
}

/** Manual logging for when you don't want to chat: pick an activity and minutes. */
function LogWorkout({ onLogged }: { onLogged: () => void }) {
  const [activity, setActivity] = useState('strength_training')
  const [minutes, setMinutes] = useState(45)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    if (!(minutes > 0 && minutes <= 600)) return setError('משך האימון צריך להיות בין 1 ל-600 דקות')
    setSaving(true)
    setError(null)
    try {
      await api.logWorkout(activity, minutes)
      onLogged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card stack">
      <h2>רישום אימון</h2>
      <div className="row">
        <select className="input" value={activity} onChange={(e) => setActivity(e.target.value)} aria-label="סוג אימון">
          {Object.entries(ACTIVITY_NAMES).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <input
          className="input" type="number" style={{ width: 90 }} value={Number.isNaN(minutes) ? '' : minutes}
          onChange={(e) => { setMinutes(e.target.valueAsNumber); setError(null) }} aria-label="דקות"
        />
        <span className="muted">דק'</span>
      </div>
      {error && <p className="error-text">{error}</p>}
      <button className="btn primary" disabled={saving} onClick={save}>{saving ? 'שומר…' : 'הוספה'}</button>
    </div>
  )
}
