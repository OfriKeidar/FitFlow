import { useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { ActivityLevel, Frequency, Goal, User, UserCreate } from '../api/types'
import { Icon, type IconName } from '../components/Icon'
import { Loader, Logo } from '../components/Logo'
import { ACTIVITY_LEVEL_LABELS, FREQUENCY_LABELS } from '../labels'

const GOALS: { id: Goal; title: string; sub: string; icon: IconName; color: string }[] = [
  { id: 'cut', title: 'חיטוב', sub: 'ירידה בשומן תוך שמירה על שריר', icon: 'trendDown', color: '#D85A30' },
  { id: 'bulk', title: 'מסה', sub: 'עלייה במסת שריר בעודף מבוקר', icon: 'trendUp', color: '#1D9E75' },
  { id: 'recomp', title: 'ריקומפוזיציה', sub: 'להוריד שומן ולבנות שריר במקביל', icon: 'arrows', color: '#7F77DD' },
  { id: 'maintain', title: 'שמירה', sub: 'לשמור על המשקל הנוכחי', icon: 'equal', color: '#888780' },
]

// Weekly rate choices per goal (kg/week). Recomp and maintain have no rate.
const RATES: Partial<Record<Goal, { value: number; label: string }[]>> = {
  cut: [
    { value: 0.25, label: 'שמרני · 0.25' },
    { value: 0.5, label: 'מומלץ · 0.5' },
    { value: 0.75, label: 'מהיר · 0.75' },
  ],
  bulk: [
    { value: 0.1, label: 'איטי · 0.1' },
    { value: 0.25, label: 'מומלץ · 0.25' },
    { value: 0.4, label: 'מהיר · 0.4' },
  ],
}

const STEPS = 4

export function Onboarding({ onDone }: { onDone: (user: User) => void }) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<UserCreate>({
    sex: 'male', age: 25, height_cm: 175, weight_kg: 75,
    activity: 'sedentary', goal: 'cut', weekly_rate_kg: 0.5,
    weigh_in_frequency: 'weekly', weekly_workout_goal: 3,
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const update = (patch: Partial<UserCreate>) => {
    setForm((f) => ({ ...f, ...patch }))
    setError(null)
  }

  function chooseGoal(goal: Goal) {
    const rates = RATES[goal]
    update({ goal, weekly_rate_kg: rates ? rates[1].value : 0 })
  }

  function validateBasics(): string | null {
    // Written as "not inside the range" so an empty field (NaN) fails too.
    const inRange = (v: number, min: number, max: number) => v >= min && v <= max
    if (!inRange(form.age, 14, 100)) return 'גיל צריך להיות בין 14 ל-100'
    if (!inRange(form.height_cm, 120, 230)) return 'גובה צריך להיות בין 120 ל-230 ס"מ'
    if (!inRange(form.weight_kg, 35, 300)) return 'משקל צריך להיות בין 35 ל-300 ק"ג'
    return null
  }

  async function next() {
    if (step === 1) {
      const problem = validateBasics()
      if (problem) return setError(problem)
    }
    if (step < STEPS) return setStep(step + 1)

    setSaving(true)
    try {
      const user = await api.createUser(form)
      // Keep the loader up for a moment - the transition feels calmer than an instant jump.
      setTimeout(() => onDone(user), 900)
    } catch (e) {
      setSaving(false)
      setError(errorMessage(e))
    }
  }

  if (saving) return <Loader message="מחשב את היעדים שלך…" />

  return (
    <div className="stack fade-in" key={step} style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: 'flex-start' }}>
        <Logo size={32} />
        <h2>FitFlow</h2>
      </div>
      <div>
        <p className="muted">שלב {step} מתוך {STEPS}</p>
        <div className="bar" style={{ marginTop: 6 }}>
          <i style={{ width: `${(step / STEPS) * 100}%`, background: 'var(--accent)' }} />
        </div>
      </div>

      {step === 1 && (
        <>
          <h1>נתחיל בהיכרות</h1>
          <div className="chips">
            {(['male', 'female'] as const).map((sex) => (
              <button key={sex} className={`chip ${form.sex === sex ? 'selected' : ''}`} onClick={() => update({ sex })}>
                {sex === 'male' ? 'גבר' : 'אישה'}
              </button>
            ))}
          </div>
          <NumberField label="גיל" value={form.age} onChange={(age) => update({ age })} />
          <NumberField label='גובה (ס"מ)' value={form.height_cm} onChange={(height_cm) => update({ height_cm })} />
          <NumberField label='משקל (ק"ג)' value={form.weight_kg} step={0.1} onChange={(weight_kg) => update({ weight_kg })} />
        </>
      )}

      {step === 2 && (
        <>
          <h1>מה המטרה שלך?</h1>
          {GOALS.map((g) => (
            <button key={g.id} className={`option ${form.goal === g.id ? 'selected' : ''}`} onClick={() => chooseGoal(g.id)}>
              <span style={{ color: g.color }}><Icon name={g.icon} size={24} /></span>
              <span>
                <div style={{ fontWeight: 500 }}>{g.title}</div>
                <div className="option-sub">{g.sub}</div>
              </span>
            </button>
          ))}
          {RATES[form.goal] && (
            <div className="card">
              <p style={{ marginBottom: 8 }}>קצב {form.goal === 'cut' ? 'ירידה' : 'עלייה'} (ק"ג בשבוע)</p>
              <div className="chips">
                {RATES[form.goal]!.map((r) => (
                  <button
                    key={r.value}
                    className={`chip ${form.weekly_rate_kg === r.value ? 'selected' : ''}`}
                    onClick={() => update({ weekly_rate_kg: r.value })}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {step === 3 && (
        <>
          <h1>קצת על השגרה שלך</h1>
          <p className="muted">רמת פעילות ביום-יום, בלי האימונים (אותם נרשום בנפרד)</p>
          <div className="chips">
            {(Object.keys(ACTIVITY_LEVEL_LABELS) as ActivityLevel[]).map((a) => (
              <button key={a} className={`chip ${form.activity === a ? 'selected' : ''}`} onClick={() => update({ activity: a })}>
                {ACTIVITY_LEVEL_LABELS[a]}
              </button>
            ))}
          </div>
          <p className="muted">כל כמה זמן תישקל?</p>
          <div className="chips">
            {(Object.keys(FREQUENCY_LABELS) as Frequency[]).map((f) => (
              <button key={f} className={`chip ${form.weigh_in_frequency === f ? 'selected' : ''}`} onClick={() => update({ weigh_in_frequency: f })}>
                {FREQUENCY_LABELS[f]}
              </button>
            ))}
          </div>
          <p className="muted">יעד אימונים בשבוע</p>
          <div className="chips">
            {[2, 3, 4, 5, 6].map((n) => (
              <button key={n} className={`chip ${form.weekly_workout_goal === n ? 'selected' : ''}`} onClick={() => update({ weekly_workout_goal: n })}>
                {n}
              </button>
            ))}
          </div>
        </>
      )}

      {step === 4 && (
        <>
          <h1>הכל מוכן</h1>
          <div className="card stack">
            <p>המערכת תחשב לך יעד קלורי ומאקרו התחלתי, ותלמד מהנתונים שלך מה חילוף החומרים האמיתי שלך.</p>
            <p className="muted">
              אחרי שבועיים של רישום ושקילות, היעדים יתעדכנו אוטומטית לפי ההתקדמות בפועל.
            </p>
          </div>
        </>
      )}

      {error && <p className="error-text">{error}</p>}
      <div className="row">
        {step > 1 ? <button className="btn" onClick={() => setStep(step - 1)}>חזרה</button> : <span />}
        <button className="btn primary" onClick={next}>{step < STEPS ? 'המשך' : 'יאללה, מתחילים'}</button>
      </div>
    </div>
  )
}

function NumberField(props: { label: string; value: number; step?: number; onChange: (v: number) => void }) {
  return (
    <label className="field">
      {props.label}
      <input
        className="input" type="number" inputMode="decimal" step={props.step ?? 1}
        value={Number.isNaN(props.value) ? '' : props.value}
        onChange={(e) => props.onChange(e.target.valueAsNumber)}
      />
    </label>
  )
}
