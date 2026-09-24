import { useEffect, useState } from 'react'
import { ApiError, api, errorMessage } from '../api/client'
import type { ActivityLevel, AuthResult, Frequency, Goal, Pace, Plan, UserCreate } from '../api/types'
import { Icon, type IconName } from '../components/Icon'
import { Loader, Logo } from '../components/Logo'
import { ACTIVITY_LEVELS, FREQUENCY_LABELS, PACE_LABELS, formatDate } from '../labels'

const GOALS: { id: Goal; title: string; sub: string; icon: IconName; color: string }[] = [
  { id: 'cut', title: 'חיטוב', sub: 'לרדת בשומן ולשמור על השריר', icon: 'trendDown', color: '#D85A30' },
  { id: 'bulk', title: 'מסה', sub: 'לעלות במסת שריר בעודף מבוקר', icon: 'trendUp', color: '#1D9E75' },
  { id: 'maintain', title: 'שמירה', sub: 'לשמור על המשקל הנוכחי', icon: 'equal', color: '#888780' },
]
const ACTIVITY_ICONS: Record<ActivityLevel, IconName> = { sedentary: 'user', light: 'run', active: 'barbell' }
const STEPS = 4

interface Props {
  onDone: (auth: AuthResult) => void
  onLogin: () => void // "I already have an account"
}

export function Onboarding({ onDone, onLogin }: Props) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<UserCreate>({
    name: '', sex: 'male', age: 25, height_cm: 175, weight_kg: 75,
    activity: 'sedentary', goal: 'cut', target_weight_kg: 70, pace: 'recommended',
    weigh_in_frequency: 'weekly', weekly_workout_goal: 3,
  })
  const [account, setAccount] = useState({ email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const update = (patch: Partial<UserCreate>) => {
    setForm((f) => ({ ...f, ...patch }))
    setError(null)
  }

  function chooseGoal(goal: Goal) {
    // Suggest a sensible starting target: 5 kg down for a cut, 3 kg up for a bulk.
    const suggested = { cut: form.weight_kg - 5, bulk: form.weight_kg + 3, maintain: null }[goal]
    update({ goal, target_weight_kg: suggested })
  }

  // Each step checks its own fields before moving on. Returns an error message, or null if OK.
  function validate(): string | null {
    const inRange = (v: number, min: number, max: number) => v >= min && v <= max // NaN fails too
    if (step === 1) {
      if (!form.name.trim()) return 'איך קוראים לך?'
      if (!inRange(form.age, 14, 100)) return 'גיל צריך להיות בין 14 ל־100'
      if (!inRange(form.height_cm, 120, 230)) return 'גובה צריך להיות בין 120 ל־230 ס"מ'
      if (!inRange(form.weight_kg, 35, 300)) return 'משקל צריך להיות בין 35 ל־300 ק"ג'
    }
    if (step === 2) return targetProblem(form)
    if (step === 4) {
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(account.email)) return 'כתובת האימייל לא תקינה'
      if (account.password.length < 8) return 'הסיסמה צריכה להיות באורך 8 תווים לפחות'
    }
    return null
  }

  async function next() {
    const problem = validate()
    if (problem) return setError(problem)
    if (step < STEPS) return setStep(step + 1)

    setSaving(true)
    try {
      const auth = await api.register({ ...form, name: form.name.trim(), ...account })
      // Keep the loader up for a moment - the transition feels calmer than an instant jump.
      setTimeout(() => onDone(auth), 900)
    } catch (e) {
      setSaving(false)
      setError(e instanceof ApiError && e.status === 409 ? 'האימייל הזה כבר רשום. אפשר להתחבר במקום.' : errorMessage(e))
    }
  }

  if (saving) return <Loader message={`מחשב את היעדים שלך, ${form.name.trim()}…`} />

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
          <h1>נעים להכיר!</h1>
          <label className="field">
            איך קוראים לך?
            <input className="input" value={form.name} maxLength={40} autoFocus
                   onChange={(e) => update({ name: e.target.value })} placeholder="השם שלך" />
          </label>
          <div className="chips">
            {(['male', 'female'] as const).map((sex) => (
              <button key={sex} className={`chip ${form.sex === sex ? 'selected' : ''}`} onClick={() => update({ sex })}>
                {sex === 'male' ? 'גבר' : 'אישה'}
              </button>
            ))}
          </div>
          <NumberField label="גיל" value={form.age} onChange={(age) => update({ age })} />
          <NumberField label='גובה (ס"מ)' value={form.height_cm} onChange={(height_cm) => update({ height_cm })} />
          <NumberField label='משקל נוכחי (ק"ג)' value={form.weight_kg} step={0.1} onChange={(weight_kg) => update({ weight_kg })} />
        </>
      )}

      {step === 2 && (
        <>
          <h1>מה המטרה שלך, {form.name.trim()}?</h1>
          {GOALS.map((g) => (
            <button key={g.id} className={`option ${form.goal === g.id ? 'selected' : ''}`} onClick={() => chooseGoal(g.id)}>
              <span style={{ color: g.color }}><Icon name={g.icon} size={24} /></span>
              <span>
                <div style={{ fontWeight: 500 }}>{g.title}</div>
                <div className="option-sub">{g.sub}</div>
              </span>
            </button>
          ))}
          {form.goal !== 'maintain' && <TargetPicker form={form} update={update} />}
        </>
      )}

      {step === 3 && (
        <>
          <h1>קצת על השגרה שלך</h1>
          <p className="muted">כמה אתה זז ביום־יום, בלי האימונים (אותם נרשום בנפרד)</p>
          {(Object.keys(ACTIVITY_LEVELS) as ActivityLevel[]).map((a) => (
            <button key={a} className={`option ${form.activity === a ? 'selected' : ''}`} onClick={() => update({ activity: a })}>
              <span style={{ color: 'var(--accent)' }}><Icon name={ACTIVITY_ICONS[a]} size={22} /></span>
              <span>
                <div style={{ fontWeight: 500 }}>{ACTIVITY_LEVELS[a].title}</div>
                <div className="option-sub">{ACTIVITY_LEVELS[a].sub}</div>
              </span>
            </button>
          ))}
          <p className="muted">כל כמה זמן תישקל?</p>
          <div className="chips">
            {(Object.keys(FREQUENCY_LABELS) as Frequency[]).map((f) => (
              <button key={f} className={`chip ${form.weigh_in_frequency === f ? 'selected' : ''}`} onClick={() => update({ weigh_in_frequency: f })}>
                {FREQUENCY_LABELS[f]}
              </button>
            ))}
          </div>
          <p className="muted">כמה אימונים בשבוע תרצה לעשות?</p>
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
          <h1>כמעט סיימנו, {form.name.trim()}!</h1>
          <p className="muted">
            אחשב לך יעד קלורי ומאקרו התחלתי, ואלמד מהנתונים שלך מה חילוף החומרים האמיתי שלך.
            נשאר רק ליצור חשבון, כדי שהנתונים יישמרו.
          </p>
          <label className="field">
            אימייל
            <input className="input" type="email" dir="ltr" autoComplete="email" value={account.email}
                   onChange={(e) => { setAccount({ ...account, email: e.target.value.trim() }); setError(null) }} />
          </label>
          <label className="field">
            סיסמה (8 תווים לפחות)
            <input className="input" type="password" dir="ltr" autoComplete="new-password" value={account.password}
                   onChange={(e) => { setAccount({ ...account, password: e.target.value }); setError(null) }} />
          </label>
        </>
      )}

      {error && <p className="error-text">{error}</p>}
      <div className="row">
        {step > 1 ? <button className="btn" onClick={() => { setStep(step - 1); setError(null) }}>חזרה</button> : <span />}
        <button className="btn primary" onClick={next}>{step < STEPS ? 'המשך' : 'יצירת חשבון'}</button>
      </div>
      {step === 1 && (
        <p className="muted" style={{ textAlign: 'center' }}>
          כבר יש לך חשבון? <button className="link-button" onClick={onLogin}>התחברות</button>
        </p>
      )}
    </div>
  )
}

/** Why the target weight doesn't fit the goal, or null if it's fine. */
function targetProblem(form: UserCreate): string | null {
  if (form.goal === 'maintain') return null
  const target = form.target_weight_kg ?? NaN
  if (!(target >= 35 && target <= 300)) return 'מה משקל היעד שלך?'
  if (form.goal === 'cut' && target >= form.weight_kg) return 'בחיטוב, משקל היעד צריך להיות נמוך מהמשקל הנוכחי'
  if (form.goal === 'bulk' && target <= form.weight_kg) return 'במסה, משקל היעד צריך להיות גבוה מהמשקל הנוכחי'
  return null
}

/** Target weight + pace, with a live "you'll get there around <date>" preview from the server. */
function TargetPicker({ form, update }: { form: UserCreate; update: (p: Partial<UserCreate>) => void }) {
  const [fetchedPlan, setPlan] = useState<Plan | null>(null)
  const valid = targetProblem(form) === null
  const plan = valid ? fetchedPlan : null // never show a plan for an invalid target

  useEffect(() => {
    if (!valid) return
    // Debounce: wait until the user stops typing before asking the server.
    const timer = setTimeout(() => {
      api.planPreview(form.goal, form.weight_kg, form.target_weight_kg!, form.pace).then(setPlan).catch(() => setPlan(null))
    }, 300)
    return () => clearTimeout(timer)
  }, [valid, form.goal, form.weight_kg, form.target_weight_kg, form.pace])

  return (
    <div className="card stack">
      <NumberField
        label='משקל יעד (ק"ג)' value={form.target_weight_kg ?? NaN} step={0.5}
        onChange={(target_weight_kg) => update({ target_weight_kg })}
      />
      <p className="muted">באיזה קצב?</p>
      <div className="chips">
        {(Object.keys(PACE_LABELS) as Pace[]).map((pace) => (
          <button key={pace} className={`chip ${form.pace === pace ? 'selected' : ''}`} onClick={() => update({ pace })}>
            {PACE_LABELS[pace]}
          </button>
        ))}
      </div>
      {plan?.target_date && (
        <div className="banner accent pop" key={plan.target_date}>
          <Icon name="flag" />
          <span>
            תגיע ל־{form.target_weight_kg} ק"ג בערך ב־<strong style={{ fontWeight: 500 }}>{formatDate(plan.target_date)}</strong>
            <span className="muted" style={{ display: 'block', color: 'inherit' }}>
              {plan.weeks_to_target} שבועות · כ־{plan.weekly_rate_kg} ק"ג בשבוע
            </span>
          </span>
        </div>
      )}
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
