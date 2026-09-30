import { useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { PendingAction } from '../api/types'
import { ActionCard } from '../components/ActionCard'
import { Icon, type IconName } from '../components/Icon'
import { Logo } from '../components/Logo'
import { useUser } from '../user'

// A message in the chat, optionally with the proposals the coach made in that reply.
interface Message {
  role: 'user' | 'assistant'
  text: string
  actions?: PendingAction[]
}

const EXAMPLES: { text: string; icon: IconName }[] = [
  { text: 'אכלתי 2 ביצים, פרוסת לחם וקוטג\'', icon: 'kitchen' },
  { text: 'רצתי חצי שעה', icon: 'run' },
  { text: 'מה לאכול לארוחת ערב?', icon: 'bulb' },
  { text: 'איך אני מתקדם השבוע?', icon: 'chart' },
]

export function Chat() {
  const user = useUser()
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<PendingAction[]>([]) // unresolved proposals from earlier
  const [loaded, setLoaded] = useState(false)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load today's conversation and any proposals still waiting for confirmation.
  useEffect(() => {
    Promise.all([api.chatHistory(), api.pendingActions()])
      .then(([history, actions]) => {
        setMessages(history)
        setPending(actions)
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoaded(true))
  }, [])

  // Keep the newest message in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function send(message: string) {
    if (!message.trim() || sending) return
    setMessages((m) => [...m, { role: 'user', text: message }])
    setText('')
    setSending(true)
    setError(null)
    try {
      const reply = await api.chat(message)
      setMessages((m) => [...m, { role: 'assistant', text: reply.reply, actions: reply.actions }])
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>רישום חכם</h1>
        <span className="muted"><Icon name="sparkles" size={16} /> AI</span>
      </div>
      <p className="muted" style={{ marginTop: -8 }}>
        כתוב בחופשיות מה אכלת או איך התאמנת. אני אחשב קלוריות וערכים, ותאשר לפני שזה נשמר.
        אפשר גם לשאול שאלות, כמו "מה לאכול לערב?"
      </p>

      {loaded && messages.length === 0 && (
        <div className="card stack fade-in">
          <div className="row" style={{ justifyContent: 'flex-start' }}>
            <Logo size={36} />
            <p>היי {user.name}! מה אכלת או איך התאמנת היום? נסה אחת מהדוגמאות:</p>
          </div>
          <div className="chips">
            {EXAMPLES.map((ex) => (
              <button key={ex.text} className="chip icon-chip" onClick={() => send(ex.text)}>
                <Icon name={ex.icon} size={14} /> {ex.text}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bubbles">
        {messages.map((m, i) => (
          <div key={i} className="stack" style={{ gap: 6 }}>
            <div className={`bubble ${m.role}`}>{m.text}</div>
            {m.actions?.map((a) => <ActionCard key={a.id} action={a} />)}
          </div>
        ))}
        {pending.length > 0 && (
          <div className="stack" style={{ gap: 6 }}>
            <p className="muted">ממתינים לאישור:</p>
            {pending.map((a) => <ActionCard key={a.id} action={a} />)}
          </div>
        )}
        {sending && (
          <div className="bubble assistant" aria-live="polite" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Logo size={22} animated /> <span className="muted">חושב…</span>
          </div>
        )}
        {error && <p className="banner danger">{error}</p>}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text) }}>
        <input
          className="input" value={text} onChange={(e) => setText(e.target.value)}
          placeholder="מה אכלת או עשית היום?" aria-label="הודעה למאמן" disabled={sending}
        />
        <button className="btn primary" disabled={sending || !text.trim()} aria-label="שליחה">
          <Icon name="send" />
        </button>
      </form>
    </>
  )
}
