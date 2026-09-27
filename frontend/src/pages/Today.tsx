import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { DailyStatus, FoodLogEntry, Goal, Workout } from '../api/types'
import { Icon, type IconName } from '../components/Icon'
import { Ring } from '../components/Ring'
import { useApi } from '../hooks/useApi'
import { useCountUp } from '../hooks/useCountUp'
import { ACTIVITY_NAMES, GOAL_LABELS, activityName, formatDate, fullDate, greeting } from '../labels'
import { useUser } from '../user'

export function Today() {
  const { data, error, reload } = useApi(api.today)

  if (error) return <p className="banner danger">לא הצלחנו לטעון את הנתונים: {error}</p>
  if (!data) return <TodaySkeleton />

  const proteinLeft = Math.round(data.remaining.protein_g)
  return (
    <>
      <Greeting day={data.day} />
      <GoalCard />
      {data.target_update && <TargetUpdateBanner status={data} />}
      <CalorieCard status={data} />
      <MacroRings status={data} />

      {data.eaten.kcal > 0 && proteinLeft > 15 && data.remaining.kcal > 150 && (
        <Link to="/meal" className="banner warning" style={{ textDecoration: 'none' }}>
          <Icon name="bulb" />
          <span>חסרים לך {proteinLeft} גר' חלבון. <u>מה לאכול?</u></span>
        </Link>
      )}

      <Meals status={data} onChange={reload} />
      <TodaysWorkouts status={data} onChange={reload} />
    </>
  )
}

function Greeting({ day }: { day: string }) {
  const user = useUser()
  const hello = greeting()
  return (
    <div className="row fade-in" style={{ alignItems: 'flex-start' }}>
      <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
        <span className="greeting-icon" style={{ marginTop: 2 }}><Icon name={hello.icon} size={26} /></span>
        <div>
          <h1>{hello.text}, {user.name}</h1>
          <p className="muted">{fullDate(day)}</p>
        </div>
      </div>
      <Link to="/profile" className="btn icon" aria-label="הפרופיל שלי" style={{ color: 'var(--text-2)' }}>
        <Icon name="user" size={24} />
      </Link>
    </div>
  )
}

function CalorieCard({ status }: { status: DailyStatus }) {
  const { target, eaten, remaining, workout_kcal, energy_balance } = status
  const shown = useCountUp(Math.abs(remaining.kcal))
  const over = remaining.kcal < 0

  return (
    <div className="card stack fade-in" style={{ alignItems: 'center', gap: 14 }}>
      <Ring
        value={eaten.kcal} max={target.kcal} size={150} stroke={12} color="var(--accent)"
        label={`נאכלו ${Math.round(eaten.kcal)} מתוך ${Math.round(target.kcal)} קלוריות`}
      >
        <div>
          <div style={{ fontSize: 30, fontWeight: 500, lineHeight: 1.1 }}>{Math.round(shown)}</div>
          <div className="muted">{over ? 'קק"ל מעל היעד' : 'קק"ל נשארו'}</div>
        </div>
      </Ring>
      <div className="grid-3" style={{ width: '100%', textAlign: 'center' }}>
        <Stat icon="flag" label="יעד" value={Math.round(target.kcal)} />
        <Stat icon="kitchen" label="נאכלו" value={Math.round(eaten.kcal)} />
        {eaten.kcal > 0
          // The energy balance only means something once the user has logged food today.
          ? <Stat icon="scale" label={energy_balance < 0 ? 'גרעון עד כה' : 'עודף עד כה'} value={Math.abs(Math.round(energy_balance))} />
          : <Stat icon="flame" label="אימון" value={Math.round(workout_kcal)} />}
      </div>
    </div>
  )
}

function Stat({ icon, label, value }: { icon: IconName; label: string; value: number }) {
  return (
    <div className="tile stack" style={{ alignItems: 'center', gap: 2 }}>
      <span className="muted" style={{ lineHeight: 0 }}><Icon name={icon} size={16} /></span>
      <div className="muted" style={{ whiteSpace: 'nowrap', fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 500 }}>{value}</div>
    </div>
  )
}

const MACROS = [
  { key: 'protein_g', label: 'חלבון', color: 'var(--accent)' },
  { key: 'carbs_g', label: 'פחמימות', color: 'var(--carbs)' },
  { key: 'fat_g', label: 'שומן', color: 'var(--fat)' },
] as const

function MacroRings({ status }: { status: DailyStatus }) {
  return (
    <div className="card grid-3 fade-in" style={{ textAlign: 'center' }}>
      {MACROS.map((m) => (
        <div key={m.key} className="stack" style={{ alignItems: 'center', gap: 4 }}>
          <Ring
            value={status.eaten[m.key]} max={status.target[m.key]} size={76} stroke={8} color={m.color}
            label={`${m.label}: ${Math.round(status.eaten[m.key])} מתוך ${Math.round(status.target[m.key])} גרם`}
          >
            <div style={{ fontSize: 16, fontWeight: 500 }}>{Math.round(status.eaten[m.key])}</div>
          </Ring>
          <div style={{ fontSize: 13 }}>{m.label}</div>
          <div className="muted" style={{ fontSize: 12 }}>מתוך {Math.round(status.target[m.key])} גר'</div>
        </div>
      ))}
    </div>
  )
}

function TargetUpdateBanner({ status }: { status: DailyStatus }) {
  const update = status.target_update!
  const change = Math.round(update.tdee - update.previous_tdee)
  return (
    <div className="banner accent pop">
      <Icon name="sparkles" />
      <span>
        עדכנו את היעדים לפי הנתונים שלך: חילוף החומרים שלך {change > 0 ? 'גבוה' : 'נמוך'} ממה שהערכנו,
        אז היעד היומי {change > 0 ? 'עלה' : 'ירד'} ב־{Math.abs(change)} קק"ל.
      </span>
    </div>
  )
}

const GOAL_ICONS: Record<Goal, IconName> = { cut: 'trendDown', bulk: 'trendUp', maintain: 'equal' }

/** The user's chosen track, always visible at the top: goal, target weight and the estimated date. */
function GoalCard() {
  const user = useUser()
  const { data: progress } = useApi(api.progress)
  const plan = progress?.plan

  let detail = 'שומרים על המשקל הנוכחי'
  if (user.target_weight_kg != null) {
    detail = `יעד ${user.target_weight_kg} ק"ג`
    if (plan?.target_date) detail += ` · עד ${formatDate(plan.target_date)} בערך`
    else if (plan && plan.weeks_to_target === null) detail += ' · הגעת ליעד!'
  }

  return (
    <Link to="/progress" className="card row fade-in" style={{ textDecoration: 'none', color: 'inherit', gap: 12 }}>
      <span className="stat-icon" style={{ background: 'var(--accent-soft)', color: 'var(--accent-text)' }}>
        <Icon name={GOAL_ICONS[user.goal]} size={20} />
      </span>
      <span style={{ flex: 1 }}>
        <div className="muted" style={{ fontSize: 12 }}>המסלול שלך</div>
        <div style={{ fontWeight: 500 }}>{GOAL_LABELS[user.goal]}</div>
        <div className="muted">{detail}</div>
      </span>
      <span className="muted">‹</span>
    </Link>
  )
}

/** A titled card with an "add" button that opens the smart log (the AI chat). */
function Section(props: { title: string; icon: IconName; addLabel: string; children: ReactNode }) {
  return (
    <div className="card stack" style={{ gap: 6 }}>
      <div className="row">
        <h2 className="row" style={{ gap: 6 }}><Icon name={props.icon} /> {props.title}</h2>
        <Link to="/log" className="btn small" style={{ textDecoration: 'none' }}>
          <Icon name="plus" size={14} /> {props.addLabel}
        </Link>
      </div>
      {props.children}
    </div>
  )
}

function Meals({ status, onChange }: { status: DailyStatus; onChange: () => void }) {
  const [editing, setEditing] = useState<number | null>(null)
  return (
    <Section title="מה אכלתי היום" icon="kitchen" addLabel="הוספת אוכל">
      {status.entries.length === 0 && (
        <p className="muted">עוד לא רשמת אוכל היום. לחץ על "הוספת אוכל" וכתוב בחופשיות מה אכלת.</p>
      )}
      {status.entries.length > 0 && <p className="muted" style={{ fontSize: 12 }}>לחיצה על פריט פותחת עריכה</p>}
      {status.entries.map((e) =>
        editing === e.id ? (
          <EditFood key={e.id} entry={e} onDone={() => { setEditing(null); onChange() }} />
        ) : (
          <button key={e.id} className="row entry-row" onClick={() => setEditing(e.id)}>
            <span>{e.servings !== 1 ? `${e.servings} × ` : ''}{e.description}</span>
            <span className="muted">{Math.round(e.kcal)} קק"ל · {Math.round(e.protein_g)} ח'</span>
          </button>
        ),
      )}
    </Section>
  )
}

/** Fix a logged food: change the amount (values scale with it) or type exact values from the label. */
function EditFood({ entry, onDone }: { entry: FoodLogEntry; onDone: () => void }) {
  const [form, setForm] = useState({
    servings: entry.servings, kcal: round1(entry.kcal), protein_g: round1(entry.protein_g),
    carbs_g: round1(entry.carbs_g), fat_g: round1(entry.fat_g),
  })
  const [touchedValues, setTouchedValues] = useState(false) // did the user type exact values?
  const [error, setError] = useState<string | null>(null)

  // Changing the amount rescales the values on screen too, so the user sees the effect right away.
  function setServings(servings: number) {
    const factor = entry.servings > 0 && servings > 0 ? servings / entry.servings : 1
    setForm({
      servings, kcal: round1(entry.kcal * factor), protein_g: round1(entry.protein_g * factor),
      carbs_g: round1(entry.carbs_g * factor), fat_g: round1(entry.fat_g * factor),
    })
  }

  async function save() {
    if (!(form.servings > 0)) return setError('הכמות צריכה להיות גדולה מאפס')
    try {
      // Send exact values only if the user typed them; otherwise the server scales by servings.
      await api.updateFood(entry.id, touchedValues ? form : { servings: form.servings })
      onDone()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function remove() {
    await api.deleteFood(entry.id)
    onDone()
  }

  const field = (key: 'kcal' | 'protein_g' | 'carbs_g' | 'fat_g', label: string) => (
    <label className="field">
      {label}
      <input className="input" type="number" inputMode="decimal" value={Number.isNaN(form[key]) ? '' : form[key]}
             onChange={(e) => { setForm({ ...form, [key]: e.target.valueAsNumber }); setTouchedValues(true); setError(null) }} />
    </label>
  )

  return (
    <div className="tile stack pop" style={{ margin: '4px 0' }}>
      <strong style={{ fontWeight: 500 }}>{entry.description}</strong>
      <label className="field">
        כמות (מנות)
        <input className="input" type="number" inputMode="decimal" step={0.5} value={Number.isNaN(form.servings) ? '' : form.servings}
               onChange={(e) => { setServings(e.target.valueAsNumber); setTouchedValues(false); setError(null) }} />
      </label>
      <div className="grid-2">
        {field('kcal', 'קלוריות')}
        {field('protein_g', "חלבון (גר')")}
        {field('carbs_g', "פחמימות (גר')")}
        {field('fat_g', "שומן (גר')")}
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="row">
        <span className="row" style={{ gap: 6 }}>
          <button className="btn primary small" onClick={save}>שמירה</button>
          <button className="btn small" onClick={onDone}>ביטול</button>
        </span>
        <button className="btn small" style={{ color: 'var(--danger)' }} onClick={remove}>
          <Icon name="trash" size={14} /> מחיקה
        </button>
      </div>
    </div>
  )
}

function TodaysWorkouts({ status, onChange }: { status: DailyStatus; onChange: () => void }) {
  const [editing, setEditing] = useState<number | null>(null)
  return (
    <Section title="האימונים שלי היום" icon="barbell" addLabel="הוספת אימון">
      {status.workouts.length === 0 && <p className="muted">עוד לא נרשם אימון היום.</p>}
      {status.workouts.map((w) =>
        editing === w.id ? (
          <EditWorkout key={w.id} workout={w} onDone={() => { setEditing(null); onChange() }} />
        ) : (
          <button key={w.id} className="row entry-row" onClick={() => setEditing(w.id)}>
            <span><Icon name="run" size={16} /> {activityName(w.activity)} · {w.minutes} דק'</span>
            <span style={{ color: 'var(--accent)' }}>+{Math.round(w.kcal)} קק"ל</span>
          </button>
        ),
      )}
    </Section>
  )
}

/** Fix a logged workout; calories burned are recomputed by the server with the same formula. */
function EditWorkout({ workout, onDone }: { workout: Workout; onDone: () => void }) {
  const [activity, setActivity] = useState(workout.activity)
  const [minutes, setMinutes] = useState(workout.minutes)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    if (!(minutes > 0 && minutes <= 600)) return setError('משך האימון צריך להיות בין 1 ל־600 דקות')
    try {
      await api.updateWorkout(workout.id, { activity, minutes })
      onDone()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function remove() {
    await api.deleteWorkout(workout.id)
    onDone()
  }

  return (
    <div className="tile stack pop" style={{ margin: '4px 0' }}>
      <div className="row">
        <select className="input" value={activity} onChange={(e) => setActivity(e.target.value)} aria-label="סוג אימון">
          {Object.entries(ACTIVITY_NAMES).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <input className="input" type="number" style={{ width: 90 }} value={Number.isNaN(minutes) ? '' : minutes}
               onChange={(e) => { setMinutes(e.target.valueAsNumber); setError(null) }} aria-label="דקות" />
        <span className="muted">דק'</span>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="row">
        <span className="row" style={{ gap: 6 }}>
          <button className="btn primary small" onClick={save}>שמירה</button>
          <button className="btn small" onClick={onDone}>ביטול</button>
        </span>
        <button className="btn small" style={{ color: 'var(--danger)' }} onClick={remove}>
          <Icon name="trash" size={14} /> מחיקה
        </button>
      </div>
    </div>
  )
}

const round1 = (x: number) => Math.round(x * 10) / 10

/** Placeholder shapes while the first load is in flight - better than a blank screen. */
function TodaySkeleton() {
  return (
    <>
      <div className="skeleton" style={{ height: 28, width: 100 }} />
      <div className="skeleton" style={{ height: 160 }} />
      <div className="skeleton" style={{ height: 120 }} />
      <div className="skeleton" style={{ height: 44 }} />
    </>
  )
}
