import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { DailyStatus, FoodLogEntry, Goal, Unit, Workout } from '../api/types'
import { Explainer } from '../components/Explainer'
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
  const { target, eaten, remaining, workout_kcal, planned_balance } = status
  const planned = Math.round(planned_balance)
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
        {planned !== 0
          // Why the target is below (or above) what the body burns: the day's planned deficit/surplus.
          ? <Stat icon="scale" label={planned < 0 ? 'גרעון מתוכנן' : 'עודף מתוכנן'} value={Math.abs(planned)} />
          : <Stat icon="flame" label="אימון" value={Math.round(workout_kcal)} />}
      </div>
      <div style={{ width: '100%' }}><CalorieExplainer status={status} /></div>
    </div>
  )
}

const KCAL_PER_KG = 7700 // mirrors domain/models.py
const fmt = (n: number) => Math.round(n).toLocaleString('he-IL')

/** "How are these numbers calculated?" - with the user's own numbers, so the target isn't a black box. */
function CalorieExplainer({ status }: { status: DailyStatus }) {
  const user = useUser()
  const { target, workout_kcal, planned_balance } = status
  const burn = target.kcal - planned_balance - workout_kcal // daily expenditure without workouts
  const gap = Math.abs(planned_balance)
  const kgPerWeek = ((gap * 7) / KCAL_PER_KG).toFixed(2)
  const base = target.kcal - workout_kcal

  const targetText = {
    cut: `היעד (${fmt(base)}) = השריפה פחות גרעון של ${fmt(gap)} קק"ל, כדי לרדת בערך ${kgPerWeek} ק"ג בשבוע.`,
    bulk: `היעד (${fmt(base)}) = השריפה ועוד עודף של ${fmt(gap)} קק"ל, כדי לעלות בערך ${kgPerWeek} ק"ג בשבוע.`,
    maintain: `היעד (${fmt(base)}) שווה לשריפה, כדי לשמור על המשקל.`,
  }[user.goal]

  return (
    <Explainer summary="איך זה מחושב?" points={[
      { icon: 'flame', text: `הגוף שלך שורף בערך ${fmt(burn)} קק"ל ביום. ההערכה מתחילה מנוסחה ומתעדכנת כל שבוע לפי ההתקדמות שלך בפועל.` },
      { icon: 'flag', text: targetText + (workout_kcal > 0 ? ` האימונים של היום הוסיפו ליעד ${fmt(workout_kcal)} קק"ל.` : '') },
      { icon: 'kitchen', text: 'נאכלו: כל מה שרשמת ואישרת היום.' },
      ...(gap > 0 ? [{
        icon: 'scale' as const,
        text: `${planned_balance < 0 ? 'גרעון' : 'עודף'} מתוכנן: ההפרש בין היעד לשריפה. זה מה שמזיז את המשקל, כי 7,700 קק"ל הן בערך קילו.`,
      }] : []),
    ]} />
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

// Protein per kg of body weight, by goal - mirrors domain/energy.py (PROTEIN_G_PER_KG).
const PROTEIN_PER_KG: Record<Goal, number> = { cut: 2.2, bulk: 1.8, maintain: 1.8 }

function MacroRings({ status }: { status: DailyStatus }) {
  const user = useUser()
  return (
    <div className="card stack fade-in">
      <div className="grid-3" style={{ textAlign: 'center' }}>
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
      <Explainer summary="למה הכמויות האלה?" points={[
        { color: 'var(--accent)', text: `חלבון: ${PROTEIN_PER_KG[user.goal]} גרם לכל ק"ג משקל גוף. ${user.goal === 'cut'
          ? 'בחיטוב צריך יותר, כדי לשמור על השריר בזמן הגרעון.' : 'זה מספיק כדי לבנות שריר ולשמור עליו.'}` },
        { color: 'var(--fat)', text: 'שומן: כרבע מהקלוריות. חשוב להורמונים ולספיגת ויטמינים.' },
        { color: 'var(--carbs)', text: 'פחמימות: כל מה שנשאר מהיעד. הן הדלק העיקרי לאימונים.' },
      ]} />
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
            <span>{e.description}{amountLabel(e) && <span className="muted"> · {amountLabel(e)}</span>}</span>
            <span className="muted">{Math.round(e.kcal)} קק"ל · {Math.round(e.protein_g)} ח'</span>
          </button>
        ),
      )}
    </Section>
  )
}

/** How much was eaten, in the most natural way: "2 × גדולה · 100 גר'" for eggs, "240 גר'" for shakshuka. */
function amountLabel(e: FoodLogEntry): string {
  if (e.grams == null) return e.servings !== 1 ? `${e.servings} מנות` : ''
  const unit = e.units[0] // the food's own portion, if it has one
  const count = unit ? e.grams / unit.grams : 0
  if (unit && Number.isInteger(count * 2)) { // whole or half portions
    const label = `${count} × ${unit.name}`
    return unit.name.includes('גרם') ? label : `${label} · ${Math.round(e.grams)} גר'`
  }
  return `${Math.round(e.grams)} גר'`
}

const GRAM: Unit = { name: 'גרם', grams: 1 }

/** Fix a logged food: change the amount - in grams or in a portion like "פרוסה" - and the values scale
 *  with it, or type exact values from the package label. */
function EditFood({ entry, onDone }: { entry: FoodLogEntry; onDone: () => void }) {
  const byWeight = entry.grams != null // foods logged with exact values only have no weight
  const units = [GRAM, ...entry.units]
  // Start in the food's own portion when the amount is a whole number of them (2 eggs), else in grams.
  const natural = entry.units[0]
  const startUnit = byWeight && natural && Number.isInteger((entry.grams! / natural.grams) * 2) ? natural : GRAM
  const [unit, setUnit] = useState(startUnit)
  const [amount, setAmount] = useState(byWeight ? round1(entry.grams! / startUnit.grams) : entry.servings)
  const [values, setValues] = useState({
    kcal: round1(entry.kcal), protein_g: round1(entry.protein_g), carbs_g: round1(entry.carbs_g), fat_g: round1(entry.fat_g),
  })
  const [touchedValues, setTouchedValues] = useState(false) // did the user type exact values?
  const [error, setError] = useState<string | null>(null)

  // The amount in the entry's own terms: grams for foods from the database, servings otherwise.
  const newAmount = byWeight ? amount * unit.grams : amount
  const oldAmount = byWeight ? entry.grams! : entry.servings

  // Changing the amount rescales the values on screen too, so the user sees the effect right away.
  function setAmountAndScale(value: number) {
    setAmount(value)
    const factor = oldAmount > 0 && value > 0 ? (byWeight ? value * unit.grams : value) / oldAmount : 1
    setValues({
      kcal: round1(entry.kcal * factor), protein_g: round1(entry.protein_g * factor),
      carbs_g: round1(entry.carbs_g * factor), fat_g: round1(entry.fat_g * factor),
    })
    setTouchedValues(false)
    setError(null)
  }

  // Switching the unit keeps the same weight: 60 g of bread = 2 slices of 30 g.
  function changeUnit(name: string) {
    const next = units.find((u) => u.name === name)!
    setUnit(next)
    setAmount(round1(newAmount / next.grams))
  }

  async function save() {
    if (!(newAmount > 0)) return setError('הכמות צריכה להיות גדולה מאפס')
    const change = byWeight ? { grams: newAmount } : { servings: newAmount }
    try {
      // Send exact values only if the user typed them; otherwise the server scales by the amount.
      await api.updateFood(entry.id, touchedValues ? { ...change, ...values } : change)
      onDone()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function remove() {
    await api.deleteFood(entry.id)
    onDone()
  }

  const field = (key: keyof typeof values, label: string) => (
    <label className="field">
      {label}
      <input className="input" type="number" inputMode="decimal" value={Number.isNaN(values[key]) ? '' : values[key]}
             onChange={(e) => { setValues({ ...values, [key]: e.target.valueAsNumber }); setTouchedValues(true); setError(null) }} />
    </label>
  )

  return (
    <div className="tile stack pop" style={{ margin: '4px 0' }}>
      <strong style={{ fontWeight: 500 }}>{entry.description}</strong>
      <div className="grid-2">
        <label className="field">
          כמות
          <input className="input" type="number" inputMode="decimal" step={unit === GRAM ? 10 : 0.5}
                 value={Number.isNaN(amount) ? '' : amount}
                 onChange={(e) => setAmountAndScale(e.target.valueAsNumber)} />
        </label>
        {byWeight ? (
          <label className="field">
            יחידה
            <select className="input" value={unit.name} onChange={(e) => changeUnit(e.target.value)}>
              {units.map((u) => (
                <option key={u.name} value={u.name}>
                  {u === GRAM || u.name.includes('גרם') ? u.name : `${u.name} (${round1(u.grams)} גר')`}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="muted" style={{ alignSelf: 'end', paddingBottom: 12 }}>מנות</span>
        )}
      </div>
      {byWeight && unit !== GRAM && <p className="muted" style={{ fontSize: 12 }}>= {Math.round(newAmount)} גרם</p>}
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
