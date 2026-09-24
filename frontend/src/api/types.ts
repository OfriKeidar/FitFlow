// TypeScript mirrors of the backend's response schemas (fitflow/api/schemas.py).
// Keeping them in one file makes it easy to see the whole API contract.

export type Goal = 'cut' | 'maintain' | 'bulk' | 'recomp'
export type ActivityLevel = 'sedentary' | 'light' | 'active'
export type Frequency = 'daily' | 'weekly' | 'monthly'
export type WorkoutCategory = 'strength' | 'cardio' | 'other'

export interface Macros {
  kcal: number
  protein_g: number
  carbs_g: number
  fat_g: number
}

export interface UserCreate {
  sex: 'male' | 'female'
  age: number
  height_cm: number
  weight_kg: number
  activity: ActivityLevel
  goal: Goal
  weekly_rate_kg: number
  weigh_in_frequency: Frequency
  weekly_workout_goal: number
}

export interface User extends Omit<UserCreate, 'weight_kg'> {
  id: number
  tdee: number
}

export interface Food {
  id: number
  name: string
  serving: string
  kcal: number
  protein_g: number
  carbs_g: number
  fat_g: number
  category: string
}

export interface FoodLogEntry extends Macros {
  id: number
  day: string
  description: string
  servings: number
}

export interface Workout {
  id: number
  day: string
  activity: string
  category: WorkoutCategory
  minutes: number
  kcal: number
}

export interface TargetUpdate {
  previous_tdee: number
  tdee: number
}

export interface DailyStatus {
  day: string
  target: Macros
  eaten: Macros
  remaining: Macros
  workout_kcal: number
  energy_balance: number
  entries: FoodLogEntry[]
  workouts: Workout[]
  target_update: TargetUpdate | null
}

export interface PantryItem {
  food: Food
  max_servings: number
}

export interface MealSuggestion {
  items: { food_id: number; food: string; serving: string; servings: number }[]
  totals: Macros
  meal_target: Macros     // what this meal aims for
  remaining_today: Macros // what's left for the whole day
}

export interface Insight {
  kind: string
  message: string
  data: Record<string, number>
}

export interface Week {
  week_start: string
  counts: Record<WorkoutCategory, number>
  goal: number
  workouts: Workout[]
}

export interface WeightPoint {
  day: string
  weight_kg: number
}

export interface Progress {
  weigh_ins: WeightPoint[]
  trend: WeightPoint[]
  tdee: number
}

export interface PendingAction {
  id: number
  kind: 'food' | 'custom_food' | 'workout' | 'weight'
  summary: string
  status: 'pending' | 'confirmed' | 'rejected'
}

export interface ChatReply {
  reply: string
  actions: PendingAction[]
}

export interface ChatHistoryItem {
  role: 'user' | 'assistant'
  text: string
}
