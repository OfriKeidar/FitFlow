import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { Food, MealSuggestion, PantryItem } from '../api/types'
import { Icon } from '../components/Icon'
import { useApi } from '../hooks/useApi'

export function Meal() {
  const pantry = useApi(api.pantry)
  // Each "different suggestion" click adds the current combination here, so the optimizer
  // (with "no-good cuts") must find the next-best one.
  const [excluded, setExcluded] = useState<number[][]>([])
  const [suggestion, setSuggestion] = useState<MealSuggestion | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (exclude: number[][]) => {
    try {
      setSuggestion(await api.mealSuggestion(exclude))
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [])

  useEffect(() => {
    // False positive: load() only calls setState after awaiting the request.
    // oxlint-disable-next-line react/set-state-in-effect
    load([])
  }, [load])

  function anotherSuggestion() {
    const current = suggestion!.items.map((i) => i.food_id)
    const next = [...excluded, current]
    setExcluded(next)
    load(next)
  }

  // After eating or changing the pantry, start over from the best suggestion.
  function refresh() {
    pantry.reload()
    setExcluded([])
    load([])
  }

  return (
    <>
      <h1>מה לאכול?</h1>
      {error && <p className="banner danger">{error}</p>}
      {!suggestion && !error && <div className="skeleton" style={{ height: 180 }} />}
      {suggestion && (
        <SuggestionCard
          data={suggestion} tries={excluded.length} onAnother={anotherSuggestion}
          onReset={() => { setExcluded([]); load([]) }} onEaten={refresh}
        />
      )}
      <FitMealCard onEaten={refresh} />
      <Pantry items={pantry.data ?? []} onChange={refresh} />
    </>
  )
}

function SuggestionCard(props: {
  data: MealSuggestion; tries: number; onAnother: () => void; onReset: () => void; onEaten: () => void
}) {
  const { data } = props
  const left = data.remaining_today

  if (data.items.length === 0) {
    return (
      <div className="card stack" style={{ textAlign: 'center' }}>
        {left.kcal <= 0 ? (
          <p>סיימת את היעד הקלורי להיום. כל הכבוד!</p>
        ) : props.tries > 0 ? (
          <>
            <p>אין עוד שילובים שונים ממה שיש בבית</p>
            <button className="btn" onClick={props.onReset}>חזרה להצעה הראשונה</button>
          </>
        ) : (
          <><p>אין עדיין הצעה</p><p className="muted">הוסף למטה מה יש לך בבית, ונמצא את השילוב הכי טוב.</p></>
        )}
      </div>
    )
  }

  return (
    <div className="card stack fade-in" style={{ border: '2px solid var(--accent)' }} key={props.tries}>
      <div className="row">
        <h2>{props.tries === 0 ? 'ההצעה שלי' : `הצעה ${props.tries + 1}`}</h2>
        <button className="btn small" onClick={props.onAnother}>
          <Icon name="refresh" size={14} /> הצעה אחרת
        </button>
      </div>
      <MealResult data={data} onEaten={props.onEaten} />
      <p className="muted" style={{ fontSize: 12 }}>
        נבחר באופטימיזציה (Integer Linear Programming) מתוך מה שיש לך בבית
      </p>
    </div>
  )
}

/** "I'm thinking of eating X and Y" -> the optimizer picks the amounts that fit what's left today. */
function FitMealCard({ onEaten }: { onEaten: () => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Food[]>([])
  const [chosen, setChosen] = useState<Food[]>([])
  const [fitted, setFitted] = useState<MealSuggestion | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function search(q: string) {
    setQuery(q)
    setResults(q.trim() ? await api.searchFoods(q.trim()) : [])
  }

  function toggle(food: Food) {
    setChosen((c) => (c.some((f) => f.id === food.id) ? c.filter((f) => f.id !== food.id) : [...c, food].slice(0, 6)))
    setFitted(null)
    setQuery('')
    setResults([])
  }

  async function fit() {
    setBusy(true)
    setError(null)
    try {
      setFitted(await api.fitMeal(chosen.map((f) => f.id)))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card stack">
      <h2><Icon name="bulb" /> יש לי רעיון לארוחה</h2>
      <p className="muted">בחר מה חשבת לאכול, ואחשב כמה מכל דבר כדי לעמוד ביעדים שנשארו לך.</p>
      {chosen.length > 0 && (
        <div className="chips">
          {chosen.map((f) => (
            <button key={f.id} className="chip selected" onClick={() => toggle(f)} aria-label={`הסרת ${f.name}`}>
              {f.name} ✕
            </button>
          ))}
        </div>
      )}
      {chosen.length < 6 && (
        <input className="input" value={query} onChange={(e) => search(e.target.value)} placeholder="חיפוש: עוף, פסטה, סלט…" />
      )}
      {results.length > 0 && (
        <div className="chips">
          {results.filter((f) => !chosen.some((c) => c.id === f.id)).map((f) => (
            <button key={f.id} className="chip" onClick={() => toggle(f)}>+ {f.name}</button>
          ))}
        </div>
      )}
      {chosen.length > 0 && !fitted && (
        <button className="btn primary" disabled={busy} onClick={fit}>{busy ? 'מחשב…' : 'תתאים לי כמויות'}</button>
      )}
      {error && <p className="error-text">{error}</p>}
      {fitted && <MealResult data={fitted} onEaten={() => { setChosen([]); setFitted(null); onEaten() }} />}
    </div>
  )
}

/** A meal (suggested or fitted): items with amounts, totals vs. this meal's target, and "I ate this". */
function MealResult({ data, onEaten }: { data: MealSuggestion; onEaten: () => void }) {
  const [logging, setLogging] = useState(false)
  const target = data.meal_target

  // "I ate this": log every item directly - the user chose it, so no AI confirmation step is needed.
  async function eatIt() {
    setLogging(true)
    for (const item of data.items) await api.logFood(item.food_id, item.servings)
    setLogging(false)
    onEaten()
  }

  const proteinOk = data.totals.protein_g >= target.protein_g * 0.9
  return (
    <div className="stack fade-in" style={{ gap: 8 }}>
      <p className="muted">
        נשארו לך היום {Math.round(data.remaining_today.kcal)} קק"ל. יעד לארוחה הזו: {Math.round(target.kcal)} קק"ל
        ו־{Math.round(target.protein_g)} גר' חלבון
      </p>
      <div className="stack" style={{ gap: 6 }}>
        {data.items.map((item) => (
          <div key={item.food_id} className="row">
            <span>{item.servings} × {item.food}</span>
            <span className="muted">{item.serving}</span>
          </div>
        ))}
      </div>
      <div className="row" style={{ borderTop: '0.5px solid var(--border)', paddingTop: 8 }}>
        <span>{Math.round(data.totals.kcal)} קק"ל · {Math.round(data.totals.protein_g)} גר' חלבון</span>
        {proteinOk && <span style={{ color: 'var(--accent)' }}><Icon name="check" size={16} /> פוגע ביעד</span>}
      </div>
      <button className="btn primary" disabled={logging} onClick={eatIt}>{logging ? 'רושם…' : 'אכלתי את זה'}</button>
    </div>
  )
}

function Pantry({ items, onChange }: { items: PantryItem[]; onChange: () => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Food[]>([])

  async function search(q: string) {
    setQuery(q)
    setResults(q.trim() ? await api.searchFoods(q.trim()) : [])
  }

  async function add(food: Food) {
    await api.setPantryItem(food.id, 2)
    setQuery('')
    setResults([])
    onChange()
  }

  async function setServings(item: PantryItem, servings: number) {
    if (servings < 1) await api.removePantryItem(item.food.id)
    else await api.setPantryItem(item.food.id, Math.min(servings, 10))
    onChange()
  }

  const inPantry = new Set(items.map((i) => i.food.id))
  return (
    <div className="card stack">
      <h2>יש לי בבית</h2>
      <p className="muted">וכמה מנות לכל היותר הייתי אוכל בארוחה אחת</p>
      {items.map((item) => (
        <div key={item.food.id} className="row">
          <span>{item.food.name} <span className="muted">· {item.food.serving}</span></span>
          <span className="row" style={{ gap: 4 }}>
            <button className="btn small" onClick={() => setServings(item, item.max_servings - 1)} aria-label="פחות">
              <Icon name="minus" size={14} />
            </button>
            <span style={{ minWidth: 20, textAlign: 'center' }}>{item.max_servings}</span>
            <button className="btn small" onClick={() => setServings(item, item.max_servings + 1)} aria-label="עוד">
              <Icon name="plus" size={14} />
            </button>
          </span>
        </div>
      ))}
      <input className="input" value={query} onChange={(e) => search(e.target.value)} placeholder="הוספת מוצר: עוף, ביצה, אורז…" />
      {results.length > 0 && (
        <div className="chips">
          {results.filter((f) => !inPantry.has(f.id)).map((f) => (
            <button key={f.id} className="chip" onClick={() => add(f)}>+ {f.name}</button>
          ))}
        </div>
      )}
    </div>
  )
}
