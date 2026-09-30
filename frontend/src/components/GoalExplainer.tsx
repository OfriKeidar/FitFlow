import type { Goal } from '../api/types'
import { GOAL_EXPLANATIONS } from '../labels'
import { Icon } from './Icon'

/** "What does this goal mean?" - collapsed by default, so it helps newcomers without cluttering the screen. */
export function GoalExplainer({ goal }: { goal: Goal }) {
  const { aim, points } = GOAL_EXPLANATIONS[goal]
  return (
    <details className="explainer" key={goal}>
      <summary><Icon name="bulb" size={14} /> מה זה אומר?</summary>
      <p style={{ fontWeight: 500 }}>{aim}</p>
      <ul>
        {points.map((p) => (
          <li key={p.text}>
            <span className="explainer-icon"><Icon name={p.icon} size={15} /></span>
            <span>{p.text}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
