import { useState } from 'react'
import { api } from '../api/client'
import type { Food, MealSuggestion, PantryItem } from '../api/types'
import { Icon } from '../components/Icon'
import { useApi } from '../hooks/useApi'

export function Meal() {
  const pantry = useApi(api.pantry)
  const suggestion = useApi(api.mealSuggestion)

  // Any pantry change can change the best meal, so refresh both.
  const refresh = () => {
    pantry.reload()
    suggestion.reload()
  }

  return (
    <>
      <h1>מה לאכול?</h1>
      <SuggestionCard data={suggestion.data} loading={suggestion.loading} error={suggestion.error} onEaten={refresh} />
      <Pantry items={pantry.data ?? []} onChange={refresh} />
    </>
  )
}

function SuggestionCard(props: { data: MealSuggestion | null; loading: boolean; error: string | null; onEaten: () => void }) {
  const [logging, setLogging] = useState(false)
  const [done, setDone] = useState(false)
  const { data } = props

  if (props.error) return <p className="banner danger">{props.error}</p>
  if (!data) return <div className="skeleton" style={{ height: 180 }} />

  const left = data.remaining_today
  const target = data.meal_target
  if (data.items.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        {left.kcal <= 0
          ? <p>סיימת את היעד הקלורי להיום. כל הכבוד!</p>
          : <><p>אין עדיין הצעה</p><p className="muted">הוסף למטה מה יש לך בבית, ונמצא את השילוב הכי טוב.</p></>}
      </div>
    )
  }

  // "I ate this": log every item directly - the user chose it, so no AI confirmation step is needed.
  async function eatIt() {
    setLogging(true)
    for (const item of data!.items) await api.logFood(item.food_id, item.servings)
    setLogging(false)
    setDone(true)
    setTimeout(() => setDone(false), 2500)
    props.onEaten()
  }

  const proteinOk = data.totals.protein_g >= target.protein_g * 0.9
  return (
    <div className="card stack fade-in" style={{ border: '2px solid var(--accent)' }}>
      <p className="muted">
        נשארו לך היום {Math.round(left.kcal)} קק"ל. יעד לארוחה הזו: {Math.round(target.kcal)} קק"ל
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
      <button className="btn primary" disabled={logging} onClick={eatIt}>
        {done ? 'נרשם!' : logging ? 'רושם…' : 'אכלתי את זה'}
      </button>
      <p className="muted" style={{ fontSize: 12 }}>
        נבחר באופטימיזציה (Integer Linear Programming) מתוך מה שיש לך בבית
      </p>
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
