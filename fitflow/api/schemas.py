"""Request / response shapes. Pydantic validates every input before it reaches our code."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, model_validator

Sex = Literal["male", "female"]
GoalName = Literal["cut", "maintain", "bulk"]
PaceName = Literal["relaxed", "recommended", "fast"]
ActivityName = Literal["sedentary", "light", "active"]
Frequency = Literal["daily", "weekly", "monthly"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MacrosOut(ORM):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

    @field_serializer("kcal", "protein_g", "carbs_g", "fat_g")
    def _round(self, v: float) -> float:
        return round(v, 1)


# --- users ---

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    sex: Sex
    age: int = Field(ge=14, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=35, le=300)
    activity: ActivityName
    goal: GoalName
    target_weight_kg: float | None = Field(default=None, ge=35, le=300)
    pace: PaceName = "recommended"
    weigh_in_frequency: Frequency = "weekly"
    weekly_workout_goal: int = Field(default=3, ge=0, le=14)

    @model_validator(mode="after")
    def target_matches_goal(self):
        check_target(self.goal, self.weight_kg, self.target_weight_kg)
        return self


def check_target(goal: str, weight_kg: float, target_kg: float | None) -> None:
    """Cutting needs a lower target, bulking a higher one; maintaining needs none."""
    if goal == "maintain":
        return
    if target_kg is None:
        raise ValueError("target_weight_kg is required for cut and bulk")
    if goal == "cut" and target_kg >= weight_kg:
        raise ValueError("for a cut, the target weight must be below the current weight")
    if goal == "bulk" and target_kg <= weight_kg:
        raise ValueError("for a bulk, the target weight must be above the current weight")


class RegisterIn(UserCreate):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserUpdate(BaseModel):
    """Every profile field can be fixed after sign-up (typos happen)."""
    name: str | None = Field(default=None, min_length=1, max_length=40)
    sex: Sex | None = None
    age: int | None = Field(default=None, ge=14, le=100)
    height_cm: float | None = Field(default=None, ge=120, le=230)
    weight_kg: float | None = Field(default=None, ge=35, le=300)  # the current weight (today's weigh-in)
    goal: GoalName | None = None
    target_weight_kg: float | None = Field(default=None, ge=35, le=300)
    pace: PaceName | None = None
    activity: ActivityName | None = None
    weigh_in_frequency: Frequency | None = None
    weekly_workout_goal: int | None = Field(default=None, ge=0, le=14)


class UserOut(ORM):
    id: int
    email: str
    name: str
    sex: Sex
    age: int
    height_cm: float
    activity: ActivityName
    goal: GoalName
    target_weight_kg: float | None
    pace: PaceName
    weigh_in_frequency: Frequency
    weekly_workout_goal: int
    tdee: float


class AuthOut(BaseModel):
    token: str
    user: UserOut


class PlanOut(BaseModel):
    """How the chosen goal plays out: speed, and when the target is reached."""
    weekly_rate_kg: float
    weeks_to_target: int | None
    target_date: date | None


# --- foods & pantry ---

class FoodOut(ORM):
    id: int
    name: str
    serving: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    category: str


class PantryItemIn(BaseModel):
    max_servings: int = Field(ge=1, le=10)


class PantryItemOut(ORM):
    food: FoodOut
    max_servings: int


# --- logging ---

class FoodLogIn(BaseModel):
    food_id: int
    servings: float = Field(gt=0, le=20)
    day: date | None = None


class CustomFoodLogIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    kcal: float = Field(ge=0, le=5000)
    protein_g: float = Field(default=0, ge=0)
    carbs_g: float = Field(default=0, ge=0)
    fat_g: float = Field(default=0, ge=0)
    day: date | None = None


class FoodLogUpdate(BaseModel):
    """Fix a logged entry. Changing only `servings` scales the nutrition values; values sent
    explicitly (e.g. from the package label) are used as-is."""
    description: str | None = Field(default=None, min_length=1, max_length=200)
    servings: float | None = Field(default=None, gt=0, le=20)
    kcal: float | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=500)
    carbs_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=500)


class SyncedWorkoutIn(BaseModel):
    """One workout read from Health Connect on the phone."""
    external_id: str = Field(min_length=1, max_length=200)
    workout_type: str = Field(max_length=60)
    start: datetime
    minutes: float = Field(gt=0, le=600)
    kcal: float | None = Field(default=None, ge=0, le=5000)  # measured by the watch, if available


class WorkoutImportIn(BaseModel):
    workouts: list[SyncedWorkoutIn] = Field(max_length=200)


class WorkoutImportOut(BaseModel):
    imported: int
    skipped: int  # already imported earlier


class WorkoutUpdate(BaseModel):
    activity: str | None = None
    minutes: float | None = Field(default=None, gt=0, le=600)


class FoodLogOut(ORM):
    id: int
    day: date
    description: str
    servings: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class WorkoutIn(BaseModel):
    activity: str
    minutes: float = Field(gt=0, le=600)
    day: date | None = None


class WorkoutOut(ORM):
    id: int
    day: date
    activity: str
    category: str
    minutes: float
    kcal: float


class WeightIn(BaseModel):
    weight_kg: float = Field(ge=35, le=300)
    day: date | None = None


class WeightOut(ORM):
    day: date
    weight_kg: float


# --- coach ---

class TargetUpdateOut(BaseModel):
    previous_tdee: float
    tdee: float


class DailyStatusOut(ORM):
    day: date
    target: MacrosOut
    eaten: MacrosOut
    remaining: MacrosOut
    workout_kcal: float
    energy_balance: float
    entries: list[FoodLogOut]
    workouts: list[WorkoutOut]
    target_update: TargetUpdateOut | None = None


class SuggestedItem(BaseModel):
    food_id: int
    food: str
    serving: str
    servings: float  # "fit my meal" works in half servings


class FitMealIn(BaseModel):
    """"I'm thinking of eating these" - the optimizer picks the amounts."""
    food_ids: list[int] = Field(min_length=1, max_length=6)
    hour: int | None = Field(default=None, ge=0, le=23)


class MealSuggestionOut(BaseModel):
    items: list[SuggestedItem]
    totals: MacrosOut
    meal_target: MacrosOut       # what this meal aims for
    remaining_today: MacrosOut   # what's left for the whole day


class InsightOut(ORM):
    kind: str
    message: str
    data: dict


class WeekOut(BaseModel):
    week_start: date
    counts: dict[str, int]
    goal: int
    workouts: list[WorkoutOut]


class ProgressOut(BaseModel):
    weigh_ins: list[WeightOut]
    trend: list[WeightOut]
    tdee: float
    start_weight_kg: float
    target_weight_kg: float | None
    plan: PlanOut


class WorkoutStatsOut(BaseModel):
    total_workouts: int
    days_since_last: int | None
    this_month: int
    minutes_this_week: float
    current_week_streak: int
    best_week_streak: int
    best_day_streak: int
    favorite_activity: str | None


# --- chat ---

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    hour: int | None = Field(default=None, ge=0, le=23)  # the user's local hour, for meal suggestions


class PendingActionOut(ORM):
    id: int
    kind: str
    summary: str
    status: str


class ChatOut(BaseModel):
    reply: str
    actions: list[PendingActionOut]


class ChatHistoryItem(BaseModel):
    role: str
    text: str
