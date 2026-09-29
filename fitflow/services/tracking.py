"""Logging food, workouts and weight, and computing the daily status."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.db import models as db
from fitflow.domain.activity import get_activity, workout_kcal
from fitflow.domain.energy import daily_targets, initial_tdee
from fitflow.domain.models import Macros, Profile, ZERO_MACROS
from fitflow.services.mappers import entry_macros, food_macros, to_profile


def current_weight(session: Session, user: db.User) -> float:
    latest = session.scalar(
        select(db.WeighInEntry.weight_kg)
        .where(db.WeighInEntry.user_id == user.id)
        .order_by(db.WeighInEntry.day.desc())
        .limit(1)
    )
    return latest if latest is not None else user.start_weight_kg


def profile_of(session: Session, user: db.User) -> Profile:
    return to_profile(user, current_weight(session, user))


def create_user(session: Session, today: date, **fields) -> db.User:
    user = db.User(**fields, tdee=0, tdee_updated_on=today)
    user.tdee = initial_tdee(to_profile(user, user.start_weight_kg))
    session.add(user)
    session.flush()
    session.add(db.WeighInEntry(user_id=user.id, day=today, weight_kg=user.start_weight_kg))
    session.commit()
    return user


def servings_for(food: db.Food, grams: float) -> float:
    """Grams -> servings of this food (240 g of a "100 גרם" food = 2.4 servings)."""
    return grams / food.grams_per_serving


def log_food(session: Session, user: db.User, food: db.Food, servings: float, day: date) -> db.FoodLogEntry:
    return log_custom_food(session, user, food.name, servings, food_macros(food).scale(servings), day, food.id,
                           grams=servings * food.grams_per_serving)


def log_custom_food(
    session: Session, user: db.User, description: str, servings: float, total: Macros, day: date,
    food_id: int | None = None, grams: float | None = None,
) -> db.FoodLogEntry:
    """Log food with explicit totals - used when the food isn't in our database."""
    entry = db.FoodLogEntry(
        user_id=user.id, day=day, food_id=food_id, description=description, servings=servings, grams=grams,
        kcal=total.kcal, protein_g=total.protein_g, carbs_g=total.carbs_g, fat_g=total.fat_g,
    )
    session.add(entry)
    session.commit()
    return entry


def log_workout(session: Session, user: db.User, activity: str, minutes: float, day: date) -> db.WorkoutEntry:
    entry = db.WorkoutEntry(
        user_id=user.id, day=day, activity=activity, minutes=minutes,
        category=get_activity(activity).category.value,
        kcal=workout_kcal(activity, minutes, current_weight(session, user)),
    )
    session.add(entry)
    session.commit()
    return entry




MACRO_FIELDS = ("kcal", "protein_g", "carbs_g", "fat_g")


def update_food_entry(session: Session, entry: db.FoodLogEntry, changes: dict) -> db.FoodLogEntry:
    """Fix a logged food. A new amount (in grams, or in servings) scales the values proportionally
    (100 g -> 150 g = x1.5), unless the user also typed exact values, which then win."""
    factor = None
    if changes.get("grams") and entry.grams:
        factor = changes["grams"] / entry.grams
    elif changes.get("servings") and entry.servings > 0:
        factor = changes["servings"] / entry.servings
    if factor is not None:
        entry.servings *= factor  # keep the amount in both units consistent
        entry.grams = entry.grams * factor if entry.grams else None
        for field in MACRO_FIELDS:
            if field not in changes:
                setattr(entry, field, getattr(entry, field) * factor)
    for field, value in changes.items():
        if field not in ("grams", "servings"):  # already applied above
            setattr(entry, field, value)
    session.commit()
    return entry


def update_workout(session: Session, user: db.User, entry: db.WorkoutEntry, activity: str | None,
                   minutes: float | None) -> db.WorkoutEntry:
    """Fix a logged workout; calories burned are recomputed with the same formula as logging."""
    entry.activity = activity or entry.activity
    entry.minutes = minutes or entry.minutes
    entry.category = get_activity(entry.activity).category.value
    entry.kcal = workout_kcal(entry.activity, entry.minutes, current_weight(session, user))
    session.commit()
    return entry


def log_weight(session: Session, user: db.User, weight_kg: float, day: date) -> db.WeighInEntry:
    """One weigh-in per day: logging again on the same day replaces the value."""
    entry = session.scalar(
        select(db.WeighInEntry).where(db.WeighInEntry.user_id == user.id, db.WeighInEntry.day == day)
    )
    if entry is None:
        entry = db.WeighInEntry(user_id=user.id, day=day, weight_kg=weight_kg)
        session.add(entry)
    else:
        entry.weight_kg = weight_kg
    session.commit()
    return entry


def correct_weight(session: Session, user: db.User, weight_kg: float, today: date) -> None:
    """The user edited their weight in the profile.

    If the only weigh-in is the one from sign-up, the sign-up weight itself was the mistake (e.g. 87
    typed instead of 78): fix it, and the starting point of the progress chart with it. Otherwise
    it's simply today's weight.
    """
    weigh_ins = list(session.scalars(select(db.WeighInEntry).where(db.WeighInEntry.user_id == user.id)))
    if len(weigh_ins) == 1:
        weigh_ins[0].weight_kg = weight_kg
        user.start_weight_kg = weight_kg
        session.flush()
    else:
        log_weight(session, user, weight_kg, today)


def food_entries(session: Session, user: db.User, day: date) -> list[db.FoodLogEntry]:
    return list(session.scalars(
        select(db.FoodLogEntry)
        .where(db.FoodLogEntry.user_id == user.id, db.FoodLogEntry.day == day)
        .order_by(db.FoodLogEntry.id)
    ))


def workout_entries(session: Session, user: db.User, start: date, end: date) -> list[db.WorkoutEntry]:
    """Workouts with start <= day <= end."""
    return list(session.scalars(
        select(db.WorkoutEntry)
        .where(db.WorkoutEntry.user_id == user.id, db.WorkoutEntry.day.between(start, end))
        .order_by(db.WorkoutEntry.day, db.WorkoutEntry.id)
    ))


@dataclass(frozen=True)
class DailyStatus:
    day: date
    target: Macros
    eaten: Macros
    remaining: Macros
    workout_kcal: float
    # The day's PLANNED balance: calorie target - expenditure (workouts count on both sides, so they
    # cancel). Negative = deficit (cut), positive = surplus (bulk), 0 = maintenance.
    # Not "eaten - expenditure so far": that compares part of a day's eating to a whole day's burn.
    planned_balance: float
    entries: list[db.FoodLogEntry]
    workouts: list[db.WorkoutEntry]


def daily_status(session: Session, user: db.User, day: date) -> DailyStatus:
    entries = food_entries(session, user, day)
    workouts = workout_entries(session, user, day, day)
    burned_in_workouts = sum(w.kcal for w in workouts)

    target = daily_targets(profile_of(session, user), user.tdee, burned_in_workouts)
    eaten = sum((entry_macros(e) for e in entries), ZERO_MACROS)
    return DailyStatus(
        day=day,
        target=target,
        eaten=eaten,
        remaining=target - eaten,
        workout_kcal=burned_in_workouts,
        planned_balance=target.kcal - (user.tdee + burned_in_workouts),
        entries=entries,
        workouts=workouts,
    )
