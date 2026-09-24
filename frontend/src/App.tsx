import { Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ApiError, api, getUserId, setUserId } from './api/client'
import { BottomNav } from './components/BottomNav'
import { Loader } from './components/Logo'
import { Chat } from './pages/Chat'
import { Meal } from './pages/Meal'
import { Onboarding } from './pages/Onboarding'
import { Today } from './pages/Today'
import { Workouts } from './pages/Workouts'

// The progress page pulls in the charting library (~400 KB), so load it only when it's opened.
const Progress = lazy(() => import('./pages/Progress').then((m) => ({ default: m.Progress })))

type Session = 'checking' | 'onboarding' | 'ready' | 'offline'

export default function App() {
  const [session, setSession] = useState<Session>(getUserId() ? 'checking' : 'onboarding')

  // A saved user id may point to a user that no longer exists (e.g. the dev database was reset).
  useEffect(() => {
    if (session !== 'checking') return
    api.me()
      .then(() => setSession('ready'))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          setUserId(null)
          setSession('onboarding')
        } else {
          setSession('offline')
        }
      })
  }, [session])

  return (
    <main className="app">
      {session === 'checking' && <Loader />}
      {session === 'offline' && (
        <div className="stack" style={{ marginTop: '30dvh', textAlign: 'center' }}>
          <p>אין חיבור לשרת</p>
          <button className="btn" onClick={() => setSession('checking')}>לנסות שוב</button>
        </div>
      )}
      {session === 'onboarding' && (
        <Onboarding onDone={(user) => { setUserId(user.id); setSession('ready') }} />
      )}
      {session === 'ready' && (
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Today />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/meal" element={<Meal />} />
            <Route path="/workouts" element={<Workouts />} />
            <Route path="/progress" element={<Suspense fallback={<Loader />}><Progress /></Suspense>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <BottomNav />
        </BrowserRouter>
      )}
    </main>
  )
}
