import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export interface ExplainerPoint {
  text: ReactNode
  icon?: IconName
  color?: string // a colored dot instead of an icon (e.g. a macro's ring color)
}

/** A collapsed "how does this work?" box: helps newcomers understand the numbers without cluttering the screen. */
export function Explainer({ summary, title, points }: { summary: string; title?: string; points: ExplainerPoint[] }) {
  return (
    <details className="explainer">
      <summary><Icon name="bulb" size={14} /> {summary}</summary>
      {title && <p style={{ fontWeight: 500 }}>{title}</p>}
      <ul>
        {points.map((p, i) => (
          <li key={i}>
            <span className="explainer-icon">
              {p.icon ? <Icon name={p.icon} size={15} /> : <i className="dot" style={{ background: p.color }} />}
            </span>
            <span>{p.text}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
