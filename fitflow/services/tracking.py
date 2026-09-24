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


def log_food(session: Session, user: db.User, food: db.Food, servings: float, day: date) -> db.FoodLogEntry:
    return log_custom_food(session, user, food.name, servings, food_macros(food).scale(servings), day, food.id)


def log_custom_food(
    session: Session, user: db.User, description: str, servings: float, total: Macros, day: date,
    food_id: int | None = None,
) -> db.FoodLogEntry:
    """Log food with explicit totals - used when the food isn't in our database."""
    entry = db.FoodLogEntry(
        user_id=user.id, day=day, food_id=food_id, description=description, servings=servings,
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
    energy_balance: float  # eaten - burned. Negative = deficit, positive = surplus.
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
        energy_balance=eaten.kcal - (user.tdee + burned_in_workouts),
        entries=entries,
        workouts=workouts,
    )
