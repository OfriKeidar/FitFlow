import { Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ApiError, LOGGED_OUT_EVENT, api, getToken, setToken } from './api/client'
import type { AuthResult, User } from './api/types'
import { BottomNav } from './components/BottomNav'
import { Loader } from './components/Logo'
import { Chat } from './pages/Chat'
import { Login } from './pages/Login'
import { Meal } from './pages/Meal'
import { Onboarding } from './pages/Onboarding'
import { Today } from './pages/Today'
import { Workouts } from './pages/Workouts'
import { UserContext } from './user'

// The progress page pulls in the charting library (~370 KB), so load it only when it's opened.
const Progress = lazy(() => import('./pages/Progress').then((m) => ({ default: m.Progress })))

type Screen = 'checking' | 'login' | 'onboarding' | 'ready' | 'offline'

export default function App() {
  const [screen, setScreen] = useState<Screen>(getToken() ? 'checking' : 'onboarding')
  const [user, setUser] = useState<User | null>(null)

  // With a saved token, load the user. An invalid or expired token triggers a logout (see client.ts).
  useEffect(() => {
    if (screen !== 'checking') return
    api.me()
      .then((me) => {
        setUser(me)
        setScreen('ready')
      })
      .catch((e) => setScreen(e instanceof ApiError && e.status === 401 ? 'login' : 'offline'))
  }, [screen])

  // Any request that gets a 401 logs out; this sends the user back to the login screen.
  useEffect(() => {
    const onLogout = () => {
      setUser(null)
      setScreen('login')
    }
    window.addEventListener(LOGGED_OUT_EVENT, onLogout)
    return () => window.removeEventListener(LOGGED_OUT_EVENT, onLogout)
  }, [])

  function loggedIn(auth: AuthResult) {
    setToken(auth.token)
    setUser(auth.user)
    setScreen('ready')
  }

  return (
    <main className="app">
      {screen === 'checking' && <Loader />}
      {screen === 'offline' && (
        <div className="stack" style={{ marginTop: '30dvh', textAlign: 'center' }}>
          <p>אין חיבור לשרת</p>
          <button className="btn" onClick={() => setScreen('checking')}>לנסות שוב</button>
        </div>
      )}
      {screen === 'login' && <Login onDone={loggedIn} onRegister={() => setScreen('onboarding')} />}
      {screen === 'onboarding' && <Onboarding onDone={loggedIn} onLogin={() => setScreen('login')} />}
      {screen === 'ready' && user && (
        <UserContext.Provider value={user}>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Today />} />
              <Route path="/log" element={<Chat />} />
              <Route path="/meal" element={<Meal />} />
              <Route path="/workouts" element={<Workouts />} />
              <Route path="/progress" element={<Suspense fallback={<Loader />}><Progress /></Suspense>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            <BottomNav />
          </BrowserRouter>
        </UserContext.Provider>
      )}
    </main>
  )
}
