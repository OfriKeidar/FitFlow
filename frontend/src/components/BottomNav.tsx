import { NavLink } from 'react-router-dom'
import { Icon, type IconName } from './Icon'

const TABS: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'היום', icon: 'home' },
  { to: '/chat', label: 'מאמן', icon: 'chat' },
  { to: '/meal', label: 'מה לאכול', icon: 'kitchen' },
  { to: '/workouts', label: 'אימונים', icon: 'barbell' },
  { to: '/progress', label: 'התקדמות', icon: 'chart' },
]

export function BottomNav() {
  return (
    <nav className="nav" aria-label="ניווט ראשי">
      <div className="nav-inner">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end>
            <Icon name={tab.icon} size={22} />
            {tab.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
