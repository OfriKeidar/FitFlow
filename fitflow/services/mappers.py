"""Translate between database rows and pure domain objects.

Keeping this in one place means the domain layer never imports SQLAlchemy.
"""

from fitflow.db import models as db
from fitflow.domain.models import (
    ActivityLevel, Experience, Food, FoodCategory, Goal, Macros, Meal, Pace, PantryItem, Profile, Sex,
    WeighIn, WeighInFrequency, Workout, WorkoutCategory,
)


def to_profile(user: db.User, current_weight_kg: float) -> Profile:
    return Profile(
        sex=Sex(user.sex),
        age=user.age,
        height_cm=user.height_cm,
        weight_kg=current_weight_kg,
        activity=ActivityLevel[user.activity.upper()],
        goal=Goal(user.goal),
        target_weight_kg=user.target_weight_kg,
        pace=Pace(user.pace),
        # A user object not saved yet has no column defaults (sign-up computes the TDEE before saving).
        experience=Experience(user.experience or Experience.INTERMEDIATE.value),
        weigh_in_frequency=WeighInFrequency[user.weigh_in_frequency.upper()],
        weekly_workout_goal=user.weekly_workout_goal,
    )


def food_macros(food: db.Food) -> Macros:
    return Macros(food.kcal, food.protein_g, food.carbs_g, food.fat_g)


def entry_macros(entry: db.FoodLogEntry) -> Macros:
    return Macros(entry.kcal, entry.protein_g, entry.carbs_g, entry.fat_g)


def to_food(food: db.Food) -> Food:
    return Food(
        name=food.name,
        serving=food.serving,
        per_serving=food_macros(food),
        category=FoodCategory(food.category),
        meals=frozenset(Meal[m] for m in food.meals.split(",")),
    )


def to_pantry_item(item: db.PantryItem) -> PantryItem:
    return PantryItem(to_food(item.food), item.max_servings)


def to_weigh_in(entry: db.WeighInEntry) -> WeighIn:
    return WeighIn(entry.day, entry.weight_kg)


def to_workout(entry: db.WorkoutEntry) -> Workout:
    return Workout(entry.day, entry.activity, WorkoutCategory(entry.category), entry.minutes, entry.kcal)
