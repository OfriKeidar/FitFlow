import { useState } from 'react'
import { ApiError, api, errorMessage } from '../api/client'
import type { AuthResult } from '../api/types'
import { Logo } from '../components/Logo'

interface Props {
  onDone: (auth: AuthResult) => void
  onRegister: () => void
}

export function Login({ onDone, onRegister }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (!email || !password) return setError('צריך אימייל וסיסמה')
    setBusy(true)
    setError(null)
    try {
      onDone(await api.login(email.trim(), password))
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401 ? 'אימייל או סיסמה שגויים' : errorMessage(e))
      setBusy(false)
    }
  }

  return (
    <form className="stack fade-in" style={{ gap: 16, marginTop: '8dvh' }} onSubmit={(e) => { e.preventDefault(); submit() }}>
      <div className="stack" style={{ alignItems: 'center' }}>
        <Logo size={64} />
        <h1>ברוך שובך</h1>
      </div>
      <label className="field">
        אימייל
        <input className="input" type="email" dir="ltr" autoComplete="email" autoFocus value={email}
               onChange={(e) => { setEmail(e.target.value); setError(null) }} />
      </label>
      <label className="field">
        סיסמה
        <input className="input" type="password" dir="ltr" autoComplete="current-password" value={password}
               onChange={(e) => { setPassword(e.target.value); setError(null) }} />
      </label>
      {error && <p className="error-text">{error}</p>}
      <button className="btn primary block" disabled={busy}>{busy ? 'מתחבר…' : 'התחברות'}</button>
      <p className="muted" style={{ textAlign: 'center' }}>
        אין לך חשבון? <button type="button" className="link-button" onClick={onRegister}>הרשמה</button>
      </p>
    </form>
  )
}
