import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { ChatReply, DailyStatus } from '../api/types'
import { ActionCard } from '../components/ActionCard'
import { Icon } from '../components/Icon'
import { MacroBar } from '../components/MacroBar'
import { useApi } from '../hooks/useApi'
import { activityName, weekdayName } from '../labels'

export function Today() {
  const { data, error, reload } = useApi(api.today)

  if (error) return <p className="banner danger">לא הצלחנו לטעון את הנתונים: {error}</p>
  if (!data) return <TodaySkeleton />

  const proteinLeft = Math.round(data.remaining.protein_g)
  return (
    <>
      <div className="page-header">
        <h1>היום</h1>
        <span className="muted">{weekdayName(data.day)}</span>
      </div>

      {data.target_update && <TargetUpdateBanner status={data} />}
      <CalorieCard status={data} />

      <div className="card stack">
        <MacroBar label="חלבון" eaten={data.eaten.protein_g} target={data.target.protein_g} color="var(--accent)" />
        <MacroBar label="פחמימות" eaten={data.eaten.carbs_g} target={data.target.carbs_g} color="var(--carbs)" />
        <MacroBar label="שומן" eaten={data.eaten.fat_g} target={data.target.fat_g} color="var(--fat)" />
      </div>

      {data.eaten.kcal > 0 && proteinLeft > 15 && data.remaining.kcal > 150 && (
        <Link to="/meal" className="banner warning" style={{ textDecoration: 'none' }}>
          <Icon name="bulb" />
          <span>חסרים לך {proteinLeft} גר' חלבון. <u>מה לאכול?</u></span>
        </Link>
      )}

      <QuickAdd onLogged={reload} />
      <FoodLog status={data} onChange={reload} />
    </>
  )
}

function CalorieCard({ status }: { status: DailyStatus }) {
  const { target, eaten, remaining, workout_kcal } = status
  const fraction = target.kcal > 0 ? Math.min(1, eaten.kcal / target.kcal) : 0
  const over = remaining.kcal < 0
  const circumference = 2 * Math.PI * 52

  return (
    <div className="card row" style={{ gap: 16 }}>
      {/* Calorie ring: fills as you eat, turns red if you go over */}
      <svg width="128" height="128" viewBox="0 0 128 128" role="img" aria-label={`נאכלו ${Math.round(eaten.kcal)} מתוך ${Math.round(target.kcal)} קלוריות`}>
        <circle cx="64" cy="64" r="52" fill="none" stroke="var(--surface-2)" strokeWidth="11" />
        <circle
          cx="64" cy="64" r="52" fill="none" strokeWidth="11" strokeLinecap="round"
          stroke={over ? 'var(--danger)' : 'var(--accent)'}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          transform="rotate(-90 64 64)"
          style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
        />
        <text x="64" y="62" textAnchor="middle" fontSize="26" fontWeight="500" fill="var(--text)">
          {Math.abs(Math.round(remaining.kcal))}
        </text>
        <text x="64" y="82" textAnchor="middle" fontSize="12" fill="var(--text-2)">
          {over ? 'קק"ל מעל היעד' : 'קק"ל נשארו'}
        </text>
      </svg>
      <div className="stack" style={{ flex: 1, gap: 6, fontSize: 14 }}>
        <div className="row"><span className="muted">יעד</span><span>{Math.round(target.kcal)}</span></div>
        <div className="row"><span className="muted">נאכלו</span><span>{Math.round(eaten.kcal)}</span></div>
        {workout_kcal > 0 && (
          <div className="row"><span className="muted">אימון</span><span style={{ color: 'var(--accent)' }}>+{Math.round(workout_kcal)}</span></div>
        )}
        {/* The energy balance only means something once the user has logged food today. */}
        {eaten.kcal > 0 && (
          <div className="row">
            <span className="muted">{status.energy_balance < 0 ? 'גרעון' : 'עודף'}</span>
            <span>{Math.abs(Math.round(status.energy_balance))}</span>
          </div>
        )}
      </div>
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

/** Free-text logging right from the dashboard - goes through the AI coach, with confirmation. */
function QuickAdd({ onLogged }: { onLogged: () => void }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<ChatReply | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function send() {
    if (!text.trim()) return
    setSending(true)
    setError(null)
    try {
      setResult(await api.chat(text.trim()))
      setText('')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="stack">
      <form className="row" onSubmit={(e) => { e.preventDefault(); send() }}>
        <input
          className="input" value={text} onChange={(e) => setText(e.target.value)}
          placeholder="אכלתי חופן שקדים ויוגורט" disabled={sending} aria-label="מה אכלת או עשית?"
        />
        <button className="btn primary" disabled={sending} aria-label="הוספה">
          <Icon name={sending ? 'sparkles' : 'plus'} />
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}
      {result && (
        <>
          <p className="muted fade-in">{result.reply}</p>
          {result.actions.map((a) => <ActionCard key={a.id} action={a} onResolved={onLogged} />)}
        </>
      )}
    </div>
  )
}

function FoodLog({ status, onChange }: { status: DailyStatus; onChange: () => void }) {
  if (status.entries.length === 0 && status.workouts.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <p>עוד לא רשמת כלום היום</p>
        <p className="muted">כתוב למעלה מה אכלת, או <Link to="/chat">דבר עם המאמן</Link></p>
      </div>
    )
  }

  async function remove(kind: 'food' | 'workout', id: number) {
    await (kind === 'food' ? api.deleteFood(id) : api.deleteWorkout(id))
    onChange()
  }

  return (
    <div className="card">
      {status.entries.map((e) => (
        <div key={e.id} className="row" style={{ padding: '6px 0', borderBottom: '0.5px solid var(--border)' }}>
          <span>{e.servings !== 1 ? `${e.servings} × ` : ''}{e.description}</span>
          <span className="row muted" style={{ gap: 4 }}>
            {Math.round(e.kcal)} · {Math.round(e.protein_g)} ח'
            <button className="btn icon" onClick={() => remove('food', e.id)} aria-label={`מחיקת ${e.description}`}>
              <Icon name="trash" size={16} />
            </button>
          </span>
        </div>
      ))}
      {status.workouts.map((w) => (
        <div key={w.id} className="row" style={{ padding: '6px 0' }}>
          <span><Icon name="run" size={16} /> {activityName(w.activity)} {w.minutes} דק'</span>
          <span className="row" style={{ gap: 4, color: 'var(--accent)' }}>
            +{Math.round(w.kcal)}
            <button className="btn icon" onClick={() => remove('workout', w.id)} aria-label="מחיקת אימון">
              <Icon name="trash" size={16} />
            </button>
          </span>
        </div>
      ))}
    </div>
  )
}

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
