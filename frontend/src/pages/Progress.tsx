import { useState } from 'react'
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { Progress as ProgressData } from '../api/types'
import { Icon } from '../components/Icon'
import { useApi } from '../hooks/useApi'
import { GOAL_LABELS, formatDate } from '../labels'

export function Progress() {
  const progress = useApi(api.progress)
  const me = useApi(api.me)

  return (
    <>
      <div className="page-header">
        <h1>התקדמות</h1>
        {me.data && <span className="muted">{GOAL_LABELS[me.data.goal]}</span>}
      </div>
      {progress.data?.target_weight_kg != null && <TargetCard data={progress.data} />}
      {progress.data ? <WeightChart data={progress.data} /> : <div className="skeleton" style={{ height: 260 }} />}
      <WeighIn onLogged={progress.reload} />
      {progress.data && (
        <div className="card stack">
          <div className="row"><h2>הוצאה קלורית יומית</h2><strong>{progress.data.tdee} קק"ל</strong></div>
          <p className="muted">
            ההערכה מתחילה מנוסחה, ומתעדכנת פעם בשבוע לפי מה שאכלת בפועל ואיך המשקל שלך השתנה.
          </p>
        </div>
      )}
      <Link to="/profile" className="btn" style={{ textDecoration: 'none', textAlign: 'center' }}>
        <Icon name="user" size={16} /> עריכת פרופיל ויעדים
      </Link>
    </>
  )
}

/** Start -> now -> target, with how much of the way is done and the estimated arrival date. */
function TargetCard({ data }: { data: ProgressData }) {
  const target = data.target_weight_kg!
  const now = data.trend.length ? data.trend[data.trend.length - 1].weight_kg : data.start_weight_kg
  const total = Math.abs(target - data.start_weight_kg)
  // "Done" only counts movement in the right direction (gaining during a cut isn't progress).
  const done = Math.max(0, Math.sign(target - data.start_weight_kg) * (now - data.start_weight_kg))
  const percent = total > 0 ? Math.min(100, (done / total) * 100) : 100
  const reached = data.plan.weeks_to_target === null

  return (
    <div className="card stack">
      <div className="row">
        <h2><Icon name="flag" /> היעד שלך</h2>
        <strong>{Math.round(percent)}%</strong>
      </div>
      <div className="bar" style={{ height: 10 }}>
        <i style={{ width: `${percent}%`, background: 'var(--accent)' }} />
      </div>
      <div className="row muted">
        <span>התחלה {data.start_weight_kg} ק"ג</span>
        <span>עכשיו {now.toFixed(1)}</span>
        <span>יעד {target} ק"ג</span>
      </div>
      {reached
        ? <p className="banner accent pop"><Icon name="trophy" /> הגעת ליעד! היעדים עברו לשמירה על המשקל.</p>
        : data.plan.target_date && (
          <p className="muted">
            בקצב הנוכחי תגיע ליעד בערך ב־{formatDate(data.plan.target_date)} ({data.plan.weeks_to_target} שבועות)
          </p>
        )}
    </div>
  )
}

function WeightChart({ data }: { data: ProgressData }) {
  if (data.weigh_ins.length < 2) {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <p>הגרף יופיע אחרי השקילה השנייה</p>
        <p className="muted">כאן תראה את השקילות שלך ואת קו המגמה המוחלק.</p>
      </div>
    )
  }

  // Merge raw weigh-ins and the smoothed trend into one series keyed by day.
  const points = data.weigh_ins.map((w, i) => ({
    day: w.day.slice(5).split('-').reverse().join('/'), // "2026-09-24" -> "24/09"
    weight: w.weight_kg,
    trend: data.trend[i]?.weight_kg,
  }))
  const first = data.trend[0].weight_kg
  const last = data.trend[data.trend.length - 1].weight_kg
  const change = last - first

  return (
    <div className="card stack">
      <div className="row">
        <span className="muted">
          <span style={{ color: 'var(--accent)' }}>━</span> מגמה  <span style={{ color: 'var(--text-3)' }}>●</span> שקילות
        </span>
        {/* dir="ltr" keeps the sign on the left of the number inside right-to-left text: "-2.1", not "2.1-" */}
        <strong><span dir="ltr">{change > 0 ? '+' : ''}{change.toFixed(1)}</span> ק"ג</strong>
      </div>
      {/* The chart reads left-to-right (time axis) even in a right-to-left page. */}
      <div dir="ltr" style={{ height: 220 }}>
        <ResponsiveContainer>
          <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--text-2)' }} tickLine={false} axisLine={false} />
            <YAxis domain={['dataMin - 1', 'dataMax + 1']} tick={{ fontSize: 11, fill: 'var(--text-2)' }}
                   tickLine={false} axisLine={false} tickFormatter={(v: number) => v.toFixed(0)} />
            <Tooltip
              contentStyle={{ background: 'var(--surface)', border: '0.5px solid var(--border)', borderRadius: 8 }}
              formatter={(v) => `${Number(v).toFixed(1)} ק"ג`}
            />
            <ZAxis range={[28, 28]} /> {/* dot size for the weigh-ins */}
            <Scatter dataKey="weight" name="שקילה" fill="var(--text-3)" />
            <Line dataKey="trend" name="מגמה" stroke="var(--accent)" strokeWidth={2.5} dot={false} type="monotone" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function WeighIn({ onLogged }: { onLogged: () => void }) {
  const [weight, setWeight] = useState<number>(NaN)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function save() {
    if (!(weight >= 35 && weight <= 300)) return setError('משקל צריך להיות בין 35 ל-300 ק"ג')
    setStatus('saving')
    setError(null)
    try {
      await api.logWeight(weight)
      setStatus('saved')
      setWeight(NaN)
      onLogged()
    } catch (e) {
      setStatus('idle')
      setError(errorMessage(e))
    }
  }

  return (
    <div className="card stack">
      <h2><Icon name="scale" /> שקילה</h2>
      <form className="row" onSubmit={(e) => { e.preventDefault(); save() }}>
        <input
          className="input" type="number" step="0.1" inputMode="decimal" placeholder='משקל היום בק"ג'
          value={Number.isNaN(weight) ? '' : weight}
          onChange={(e) => { setWeight(e.target.valueAsNumber); setStatus('idle'); setError(null) }}
        />
        <button className="btn primary" disabled={status === 'saving'}>שמירה</button>
      </form>
      {status === 'saved' && <p className="pop" style={{ color: 'var(--accent)' }}><Icon name="check" size={16} /> נשמר</p>}
      {error && <p className="error-text">{error}</p>}
    </div>
  )
}
