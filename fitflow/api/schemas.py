"""Request / response shapes. Pydantic validates every input before it reaches our code."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

Sex = Literal["male", "female"]
GoalName = Literal["cut", "maintain", "bulk", "recomp"]
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
    sex: Sex
    age: int = Field(ge=14, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=35, le=300)
    activity: ActivityName
    goal: GoalName
    weekly_rate_kg: float = Field(default=0.0, ge=0, le=1.5)
    weigh_in_frequency: Frequency = "weekly"
    weekly_workout_goal: int = Field(default=3, ge=0, le=14)


class UserUpdate(BaseModel):
    goal: GoalName | None = None
    weekly_rate_kg: float | None = Field(default=None, ge=0, le=1.5)
    activity: ActivityName | None = None
    weigh_in_frequency: Frequency | None = None
    weekly_workout_goal: int | None = Field(default=None, ge=0, le=14)


class UserOut(ORM):
    id: int
    sex: Sex
    age: int
    height_cm: float
    activity: ActivityName
    goal: GoalName
    weekly_rate_kg: float
    weigh_in_frequency: Frequency
    weekly_workout_goal: int
    tdee: float


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
    servings: int


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
