import type { Goal } from '../api/types'
import { GOAL_EXPLANATIONS } from '../labels'
import { Explainer } from './Explainer'

/** "What does this goal mean?" under the goal choice (onboarding and profile). */
export function GoalExplainer({ goal }: { goal: Goal }) {
  const { aim, points } = GOAL_EXPLANATIONS[goal]
  return <Explainer key={goal} summary="מה זה אומר?" title={aim} points={points} />
}
