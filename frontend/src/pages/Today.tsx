import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { ChatReply, DailyStatus } from '../api/types'
import { ActionCard } from '../components/ActionCard'
import { Icon, type IconName } from '../components/Icon'
import { Ring } from '../components/Ring'
import { useApi } from '../hooks/useApi'
import { useCountUp } from '../hooks/useCountUp'
import { activityName, greeting, weekdayName } from '../labels'
import { useUser } from '../user'

export function Today() {
  const { data, error, reload } = useApi(api.today)

  if (error) return <p className="banner danger">לא הצלחנו לטעון את הנתונים: {error}</p>
  if (!data) return <TodaySkeleton />

  const proteinLeft = Math.round(data.remaining.protein_g)
  return (
    <>
      <Greeting day={data.day} />
      {data.target_update && <TargetUpdateBanner status={data} />}
      <CalorieCard status={data} />
      <MacroRings status={data} />

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

function Greeting({ day }: { day: string }) {
  const user = useUser()
  const hello = greeting()
  return (
    <div className="page-header fade-in">
      <div className="row" style={{ gap: 8 }}>
        <span className="greeting-icon"><Icon name={hello.icon} size={26} /></span>
        <h1>{hello.text}, {user.name}</h1>
      </div>
      <span className="muted">{weekdayName(day)}</span>
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
        <div className="empty-icon"><Icon name="kitchen" size={28} /></div>
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
