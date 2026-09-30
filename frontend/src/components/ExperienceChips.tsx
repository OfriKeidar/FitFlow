import type { Experience } from '../api/types'
import { EXPERIENCE_LABELS } from '../labels'

/** Pick training experience (sets the bulking pace), with a short explanation of the selected level. */
export function ExperienceChips({ value, onChange }: { value: Experience; onChange: (e: Experience) => void }) {
  return (
    <>
      <div className="chips">
        {(Object.keys(EXPERIENCE_LABELS) as Experience[]).map((e) => (
          <button key={e} className={`chip ${value === e ? 'selected' : ''}`} onClick={() => onChange(e)}>
            {EXPERIENCE_LABELS[e].title}
          </button>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 12 }}>{EXPERIENCE_LABELS[value].sub}</p>
    </>
  )
}
