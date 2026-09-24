"""Plain data types shared by all domain modules."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

# Energy stored in ~1 kg of body fat. The single most important constant in the system.
KCAL_PER_KG = 7700


class Sex(Enum):
    MALE = "male"
    FEMALE = "female"


class Goal(Enum):
    CUT = "cut"
    MAINTAIN = "maintain"
    BULK = "bulk"


class Pace(Enum):
    """How fast the user wants to reach their target weight (see energy.WEEKLY_RATE_PCT)."""
    RELAXED = "relaxed"
    RECOMMENDED = "recommended"
    FAST = "fast"


class ActivityLevel(Enum):
    """Daily lifestyle activity EXCLUDING logged workouts (those are added separately)."""
    SEDENTARY = 1.2   # desk job
    LIGHT = 1.375     # on your feet part of the day
    ACTIVE = 1.55     # physical job


class WeighInFrequency(Enum):
    DAILY = 1
    WEEKLY = 7
    MONTHLY = 30


class Meal(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class WorkoutCategory(Enum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    OTHER = "other"


class FoodCategory(Enum):
    PROTEIN = "protein"
    CARB = "carb"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    DAIRY = "dairy"
    FAT = "fat"


@dataclass(frozen=True)
class Profile:
    sex: Sex
    age: int
    height_cm: float
    weight_kg: float
    activity: ActivityLevel
    goal: Goal
    target_weight_kg: float | None = None  # None for "maintain"
    pace: Pace = Pace.RECOMMENDED
    weigh_in_frequency: WeighInFrequency = WeighInFrequency.WEEKLY
    weekly_workout_goal: int = 3


@dataclass(frozen=True)
class Macros:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(
            self.kcal + other.kcal,
            self.protein_g + other.protein_g,
            self.carbs_g + other.carbs_g,
            self.fat_g + other.fat_g,
        )

    def __sub__(self, other: "Macros") -> "Macros":
        return Macros(
            self.kcal - other.kcal,
            self.protein_g - other.protein_g,
            self.carbs_g - other.carbs_g,
            self.fat_g - other.fat_g,
        )

    def scale(self, factor: float) -> "Macros":
        return Macros(
            self.kcal * factor,
            self.protein_g * factor,
            self.carbs_g * factor,
            self.fat_g * factor,
        )


ZERO_MACROS = Macros(0, 0, 0, 0)


@dataclass(frozen=True)
class Food:
    """Nutrition values are per ONE serving (e.g. 1 egg, 100 g chicken, 1 slice of bread)."""
    name: str
    serving: str
    per_serving: Macros
    category: FoodCategory
    meals: frozenset[Meal] = field(default_factory=lambda: frozenset(Meal))


@dataclass(frozen=True)
class PantryItem:
    """A food the user has at home, and the most servings they can/would eat in one meal."""
    food: Food
    max_servings: int


@dataclass(frozen=True)
class WeighIn:
    day: date
    weight_kg: float


@dataclass(frozen=True)
class Workout:
    day: date
    activity: str
    category: WorkoutCategory
    minutes: float
    kcal: float


@dataclass(frozen=True)
class DaySummary:
    """Everything that happened on one day - the input for insights."""
    day: date
    intake: Macros
    target: Macros
    workouts: tuple[Workout, ...] = ()
