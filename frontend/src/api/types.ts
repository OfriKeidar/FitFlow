// TypeScript mirrors of the backend's response schemas (fitflow/api/schemas.py).
// Keeping them in one file makes it easy to see the whole API contract.

export type Goal = 'cut' | 'maintain' | 'bulk'
export type Pace = 'relaxed' | 'recommended' | 'fast'
export type Experience = 'beginner' | 'intermediate' | 'advanced' // years of strength training
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
  name: string
  sex: 'male' | 'female'
  age: number
  height_cm: number
  weight_kg: number
  activity: ActivityLevel
  goal: Goal
  target_weight_kg: number | null // null when maintaining
  pace: Pace
  experience: Experience
  weigh_in_frequency: Frequency
  weekly_workout_goal: number
}

export interface RegisterData extends UserCreate {
  email: string
  password: string
}

export interface User extends Omit<UserCreate, 'weight_kg'> {
  id: number
  email: string
  tdee: number
}

export interface AuthResult {
  token: string
  user: User
}

/** A portion and its weight, e.g. { name: 'פרוסה', grams: 30 }. */
export interface Unit {
  name: string
  grams: number
}

export interface Food {
  id: number
  name: string
  serving: string
  grams_per_serving: number
  units: Unit[]
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
  grams: number | null // null for foods logged with exact values only
  units: Unit[]        // portions the amount can be edited in, besides grams
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
  planned_balance: number // target - expenditure: negative = planned deficit
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

export interface FoodLogUpdate {
  description?: string
  grams?: number
  servings?: number
  kcal?: number
  protein_g?: number
  carbs_g?: number
  fat_g?: number
}

export interface UserUpdate extends Partial<Omit<UserCreate, 'target_weight_kg'>> {
  target_weight_kg?: number | null
}

export interface Plan {
  weekly_rate_kg: number
  weeks_to_target: number | null
  target_date: string | null
}

export interface Progress {
  weigh_ins: WeightPoint[]
  trend: WeightPoint[]
  tdee: number
  start_weight_kg: number
  target_weight_kg: number | null
  plan: Plan
}

export interface WorkoutStats {
  total_workouts: number
  days_since_last: number | null
  this_month: number
  minutes_this_week: number
  current_week_streak: number
  best_week_streak: number
  best_day_streak: number
  favorite_activity: string | null
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
