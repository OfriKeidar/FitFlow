"""The "smart" features: adaptive targets, meal suggestions, insights and progress."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.db import models as db
from fitflow.domain.energy import daily_targets
from fitflow.domain.insights import Insight, generate_insights, week_start, weekly_workout_counts
from fitflow.domain.models import DaySummary, Macros, WeighIn, WorkoutCategory, ZERO_MACROS
from fitflow.domain.optimizer import MealSuggestion, meal_for_hour, suggest_meal
from fitflow.domain.trend import TdeeUpdate, adaptive_tdee, weight_trend
from fitflow.services.mappers import entry_macros, to_pantry_item, to_weigh_in, to_workout
from fitflow.services.tracking import daily_status, profile_of, workout_entries

UPDATE_EVERY_DAYS = 7
MIN_WINDOW_DAYS = 28
INSIGHT_WINDOW_DAYS = 28


def _weigh_ins(session: Session, user: db.User, since: date | None = None) -> list[WeighIn]:
    query = select(db.WeighInEntry).where(db.WeighInEntry.user_id == user.id)
    if since is not None:
        query = query.where(db.WeighInEntry.day >= since)
    return [to_weigh_in(w) for w in session.scalars(query.order_by(db.WeighInEntry.day))]


def _intake_by_day(session: Session, user: db.User, start: date, end: date) -> dict[date, Macros]:
    totals: dict[date, Macros] = defaultdict(lambda: ZERO_MACROS)
    entries = session.scalars(
        select(db.FoodLogEntry)
        .where(db.FoodLogEntry.user_id == user.id, db.FoodLogEntry.day.between(start, end))
    )
    for e in entries:
        totals[e.day] = totals[e.day] + entry_macros(e)
    return dict(totals)


def update_targets_if_due(session: Session, user: db.User, today: date) -> TdeeUpdate | None:
    """Re-learn the user's TDEE once a week from their weigh-ins and food log."""
    if (today - user.tdee_updated_on).days < UPDATE_EVERY_DAYS:
        return None

    # Rare weigh-ins need a longer window to contain enough readings.
    frequency_days = profile_of(session, user).weigh_in_frequency.value
    start = today - timedelta(days=max(MIN_WINDOW_DAYS, 3 * frequency_days))

    intake = {d: m.kcal for d, m in _intake_by_day(session, user, start, today).items()}
    workouts: dict[date, float] = defaultdict(float)
    for w in workout_entries(session, user, start, today):
        workouts[w.day] += w.kcal

    update = adaptive_tdee(user.tdee, _weigh_ins(session, user, since=start), intake, workouts)
    user.tdee = update.tdee
    user.tdee_updated_on = today
    session.commit()
    return update


def suggest_meal_now(session: Session, user: db.User, day: date, hour: int) -> MealSuggestion:
    remaining = daily_status(session, user, day).remaining
    pantry = [to_pantry_item(p) for p in user.pantry]
    disliked = frozenset(d.food.name for d in user.disliked)
    return suggest_meal(pantry, remaining, meal_for_hour(hour), disliked)


def insights(session: Session, user: db.User, today: date) -> list[Insight]:
    start = today - timedelta(days=INSIGHT_WINDOW_DAYS)
    profile = profile_of(session, user)
    workouts = [to_workout(w) for w in workout_entries(session, user, start - timedelta(days=90), today)]

    workouts_by_day = defaultdict(list)
    for w in workouts:
        workouts_by_day[w.day].append(w)

    # Only days with logged food - an empty day means "didn't log", not "ate nothing".
    days = [
        DaySummary(
            day=d,
            intake=intake,
            target=daily_targets(profile, user.tdee, sum(w.kcal for w in workouts_by_day[d])),
            workouts=tuple(workouts_by_day[d]),
        )
        for d, intake in sorted(_intake_by_day(session, user, start, today - timedelta(days=1)).items())
    ]
    return generate_insights(days, workouts, user.weekly_workout_goal, today)


@dataclass(frozen=True)
class WeekSummary:
    week_start: date
    counts: dict[WorkoutCategory, int]
    goal: int
    workouts: list[db.WorkoutEntry]


def week_summary(session: Session, user: db.User, day: date) -> WeekSummary:
    start = week_start(day)
    entries = workout_entries(session, user, start, start + timedelta(days=6))
    counts = weekly_workout_counts([to_workout(w) for w in entries], day)
    return WeekSummary(start, counts, user.weekly_workout_goal, entries)


@dataclass(frozen=True)
class Progress:
    weigh_ins: list[WeighIn]
    trend: list[WeighIn]
    tdee: float


def progress(session: Session, user: db.User) -> Progress:
    weigh_ins = _weigh_ins(session, user)
    return Progress(weigh_ins, weight_trend(weigh_ins), user.tdee)
