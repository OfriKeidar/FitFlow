import { useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { PendingAction } from '../api/types'
import { Icon } from './Icon'

const TITLES: Record<PendingAction['kind'], string> = {
  food: 'רישום אוכל',
  custom_food: 'רישום אוכל (הערכה)',
  workout: 'רישום אימון',
  weight: 'רישום שקילה',
}

interface Props {
  action: PendingAction
  onResolved?: () => void // called after confirm/reject, so the page can refresh its numbers
}

/**
 * A proposal from the AI coach, with Confirm / Reject buttons.
 * This is the "human in the loop": nothing the AI proposes is saved until the user confirms here.
 */
export function ActionCard({ action, onResolved }: Props) {
  const [status, setStatus] = useState(action.status)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function resolve(confirm: boolean) {
    setBusy(true)
    setError(null)
    try {
      const updated = confirm ? await api.confirmAction(action.id) : await api.rejectAction(action.id)
      setStatus(updated.status)
      onResolved?.()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card fade-in" style={{ borderColor: status === 'pending' ? 'var(--accent)' : undefined }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <strong style={{ fontWeight: 500 }}>{TITLES[action.kind]}</strong>
        {status === 'confirmed' && <span className="pop" style={{ color: 'var(--accent)' }}><Icon name="check" /> נרשם</span>}
        {status === 'rejected' && <span className="muted">בוטל</span>}
      </div>
      <p className="muted" style={{ whiteSpace: 'pre-line' }}>{action.summary}</p>
      {status === 'pending' && (
        <div className="row" style={{ justifyContent: 'flex-start', marginTop: 10 }}>
          <button className="btn primary small" disabled={busy} onClick={() => resolve(true)}>אישור</button>
          <button className="btn small" disabled={busy} onClick={() => resolve(false)}>ביטול</button>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
    </div>
  )
}
