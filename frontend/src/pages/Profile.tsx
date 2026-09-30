import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage, logout } from '../api/client'
import type { ActivityLevel, Frequency, Goal, Pace, User, UserUpdate } from '../api/types'
import { ExperienceChips } from '../components/ExperienceChips'
import { GoalExplainer } from '../components/GoalExplainer'
import { Icon } from '../components/Icon'
import { useApi } from '../hooks/useApi'
import { ACTIVITY_ICONS, ACTIVITY_LEVELS, FREQUENCY_LABELS, GOAL_LABELS, PACE_LABELS, WORKOUT_GOAL_OPTIONS } from '../labels'
import { useSetUser, useUser } from '../user'

/** Everything from sign-up can be fixed here - typos in weight or height happen. */
export function Profile() {
  const user = useUser()
  const progress = useApi(api.progress)
  const lastWeight = progress.data?.weigh_ins.at(-1)?.weight_kg

  return (
    <>
      <div className="page-header">
        <h1>הפרופיל שלי</h1>
        <Link to="/" className="muted">חזרה</Link>
      </div>
      {/* Wait for the current weight, so the form starts with real values. `key` resets it after saving. */}
      {progress.data ? <ProfileForm key={user.tdee} user={user} currentWeight={lastWeight ?? NaN} onSaved={progress.reload} />
                     : <div className="skeleton" style={{ height: 400 }} />}
      <p className="muted" style={{ fontSize: 12 }}>מחובר בתור {user.email}</p>
      <button className="btn" onClick={logout}><Icon name="logout" size={16} /> התנתקות</button>
    </>
  )
}

function ProfileForm({ user, currentWeight, onSaved }: { user: User; currentWeight: number; onSaved: () => void }) {
  const setUser = useSetUser()
  const [form, setForm] = useState({
    name: user.name, sex: user.sex, age: user.age, height_cm: user.height_cm, weight_kg: currentWeight,
    goal: user.goal, target_weight_kg: user.target_weight_kg ?? NaN, pace: user.pace, experience: user.experience,
    activity: user.activity,
    weigh_in_frequency: user.weigh_in_frequency, weekly_workout_goal: user.weekly_workout_goal,
  })
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)

  const update = (patch: Partial<typeof form>) => {
    setForm((f) => ({ ...f, ...patch }))
    setStatus('idle')
    setError(null)
  }

  function problem(): string | null {
    const inRange = (v: number, min: number, max: number) => v >= min && v <= max // NaN fails too
    if (!form.name.trim()) return 'השם לא יכול להיות ריק'
    if (!inRange(form.age, 14, 100)) return 'גיל צריך להיות בין 14 ל־100'
    if (!inRange(form.height_cm, 120, 230)) return 'גובה צריך להיות בין 120 ל־230 ס"מ'
    if (!inRange(form.weight_kg, 35, 300)) return 'משקל צריך להיות בין 35 ל־300 ק"ג'
    if (form.goal !== 'maintain') {
      if (!inRange(form.target_weight_kg, 35, 300)) return 'מה משקל היעד שלך?'
      if (form.goal === 'cut' && form.target_weight_kg >= form.weight_kg) return 'בחיטוב, משקל היעד צריך להיות נמוך מהמשקל הנוכחי'
      if (form.goal === 'bulk' && form.target_weight_kg <= form.weight_kg) return 'במסה, משקל היעד צריך להיות גבוה מהמשקל הנוכחי'
    }
    return null
  }

  async function save() {
    const p = problem()
    if (p) return setError(p)
    setStatus('saving')
    // Send only what changed: e.g. an unchanged weight must not create a new weigh-in.
    const changes: UserUpdate = {}
    if (form.name.trim() !== user.name) changes.name = form.name.trim()
    if (form.sex !== user.sex) changes.sex = form.sex
    if (form.age !== user.age) changes.age = form.age
    if (form.height_cm !== user.height_cm) changes.height_cm = form.height_cm
    if (form.weight_kg !== currentWeight) changes.weight_kg = form.weight_kg
    if (form.goal !== user.goal) changes.goal = form.goal
    const target = form.goal === 'maintain' ? null : form.target_weight_kg
    if (target !== user.target_weight_kg) changes.target_weight_kg = target
    if (form.pace !== user.pace) changes.pace = form.pace
    if (form.experience !== user.experience) changes.experience = form.experience
    if (form.activity !== user.activity) changes.activity = form.activity
    if (form.weigh_in_frequency !== user.weigh_in_frequency) changes.weigh_in_frequency = form.weigh_in_frequency
    if (form.weekly_workout_goal !== user.weekly_workout_goal) changes.weekly_workout_goal = form.weekly_workout_goal
    try {
      setUser(await api.updateMe(changes)) // updates the name, goal... on every screen
      setStatus('saved')
      onSaved()
    } catch (e) {
      setStatus('idle')
      setError(errorMessage(e))
    }
  }

  const number = (key: 'age' | 'height_cm' | 'weight_kg' | 'target_weight_kg', label: string, step = 1) => (
    <label className="field">
      {label}
      <input className="input" type="number" inputMode="decimal" step={step} value={Number.isNaN(form[key]) ? '' : form[key]}
             onChange={(e) => update({ [key]: e.target.valueAsNumber })} />
    </label>
  )

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="card stack">
        <h2 className="row" style={{ gap: 6, justifyContent: 'flex-start' }}><Icon name="user" /> פרטים אישיים</h2>
        <label className="field">
          שם
          <input className="input" value={form.name} maxLength={40} onChange={(e) => update({ name: e.target.value })} />
        </label>
        <div className="chips">
          {(['male', 'female'] as const).map((sex) => (
            <button key={sex} className={`chip ${form.sex === sex ? 'selected' : ''}`} onClick={() => update({ sex })}>
              {sex === 'male' ? 'גבר' : 'אישה'}
            </button>
          ))}
        </div>
        <div className="grid-2">
          {number('age', 'גיל')}
          {number('height_cm', 'גובה (ס"מ)')}
        </div>
        {number('weight_kg', 'משקל נוכחי (ק"ג)', 0.1)}
        <p className="muted" style={{ fontSize: 12 }}>
          אם זה עדיין משקל ההרשמה, התיקון יחליף אותו. אחרת הוא יירשם כשקילה של היום.
        </p>
      </div>

      <div className="card stack">
        <h2 className="row" style={{ gap: 6, justifyContent: 'flex-start' }}><Icon name="flag" /> המטרה</h2>
        <div className="chips">
          {(Object.keys(GOAL_LABELS) as Goal[]).map((goal) => (
            <button key={goal} className={`chip ${form.goal === goal ? 'selected' : ''}`} onClick={() => update({ goal })}>
              {GOAL_LABELS[goal]}
            </button>
          ))}
        </div>
        <GoalExplainer goal={form.goal} />
        {form.goal !== 'maintain' && (
          <>
            {number('target_weight_kg', 'משקל יעד (ק"ג)', 0.5)}
            {form.goal === 'bulk' && (
              <>
                <p className="muted">ניסיון באימוני כוח (קובע את קצב המסה)</p>
                <ExperienceChips value={form.experience} onChange={(experience) => update({ experience })} />
              </>
            )}
            <p className="muted">קצב</p>
            <div className="chips">
              {(Object.keys(PACE_LABELS) as Pace[]).map((pace) => (
                <button key={pace} className={`chip ${form.pace === pace ? 'selected' : ''}`} onClick={() => update({ pace })}>
                  {PACE_LABELS[pace]}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card stack">
        <h2 className="row" style={{ gap: 6, justifyContent: 'flex-start' }}><Icon name="calendar" /> שגרה</h2>
        <div className="chips">
          {(Object.keys(ACTIVITY_LEVELS) as ActivityLevel[]).map((a) => (
            <button key={a} className={`chip icon-chip ${form.activity === a ? 'selected' : ''}`} onClick={() => update({ activity: a })}>
              <Icon name={ACTIVITY_ICONS[a]} size={14} /> {ACTIVITY_LEVELS[a].title}
            </button>
          ))}
        </div>
        <p className="muted">תדירות שקילה</p>
        <div className="chips">
          {(Object.keys(FREQUENCY_LABELS) as Frequency[]).map((f) => (
            <button key={f} className={`chip ${form.weigh_in_frequency === f ? 'selected' : ''}`} onClick={() => update({ weigh_in_frequency: f })}>
              {FREQUENCY_LABELS[f]}
            </button>
          ))}
        </div>
        <p className="muted">יעד אימונים בשבוע</p>
        <div className="chips">
          {WORKOUT_GOAL_OPTIONS.map((n) => (
            <button key={n} className={`chip ${form.weekly_workout_goal === n ? 'selected' : ''}`} onClick={() => update({ weekly_workout_goal: n })}>
              {n}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}
      {status === 'saved' && <p className="banner accent pop"><Icon name="check" /> נשמר. היעדים עודכנו בהתאם.</p>}
      <button className="btn primary block" disabled={status === 'saving'} onClick={save}>
        {status === 'saving' ? 'שומר…' : 'שמירת שינויים'}
      </button>
    </div>
  )
}
