import { NavLink } from 'react-router-dom'
import { Icon, type IconName } from './Icon'

const TABS: { to: string; label: string; icon: IconName; main?: boolean }[] = [
  { to: '/', label: 'היום', icon: 'home' },
  { to: '/meal', label: 'מה לאכול', icon: 'kitchen' },
  { to: '/log', label: 'רישום', icon: 'plus', main: true }, // the smart log: chat with the AI
  { to: '/workouts', label: 'אימונים', icon: 'barbell' },
  { to: '/progress', label: 'התקדמות', icon: 'chart' },
]

export function BottomNav() {
  return (
    <nav className="nav" aria-label="ניווט ראשי">
      <div className="nav-inner">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end className={tab.main ? 'nav-main' : undefined}>
            {tab.main
              ? <span className="nav-main-button"><Icon name={tab.icon} size={26} /></span>
              : <Icon name={tab.icon} size={22} />}
            {tab.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
