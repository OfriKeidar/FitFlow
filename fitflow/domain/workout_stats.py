"""Fun, motivating numbers about the user's workout history."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from fitflow.domain.insights import week_start, workout_streak_weeks
from fitflow.domain.models import Workout


@dataclass(frozen=True)
class WorkoutStats:
    total_workouts: int
    days_since_last: int | None     # None if the user never trained
    this_month: int                 # workouts since the 1st of this month
    minutes_this_week: float
    current_week_streak: int        # consecutive weeks (ending now) that met the weekly goal
    best_week_streak: int           # the longest such run ever
    best_day_streak: int            # most consecutive days with a workout
    favorite_activity: str | None   # the most frequent activity


def longest_run(sorted_items: list, is_next) -> int:
    """Length of the longest run where each item "follows" the previous one (is_next(prev, cur))."""
    best = current = 0
    for i, item in enumerate(sorted_items):
        current = current + 1 if i > 0 and is_next(sorted_items[i - 1], item) else 1
        best = max(best, current)
    return best


def best_week_streak(workouts: list[Workout], weekly_goal: int) -> int:
    counts = Counter(week_start(w.day) for w in workouts)
    good_weeks = sorted(week for week, n in counts.items() if n >= weekly_goal)
    return longest_run(good_weeks, lambda prev, cur: cur - prev == timedelta(days=7))


def workout_stats(workouts: list[Workout], weekly_goal: int, today: date) -> WorkoutStats:
    if not workouts:
        return WorkoutStats(0, None, 0, 0, 0, 0, 0, None)

    days = sorted({w.day for w in workouts})
    this_week = week_start(today)
    return WorkoutStats(
        total_workouts=len(workouts),
        days_since_last=(today - days[-1]).days,
        this_month=sum(1 for w in workouts if w.day.year == today.year and w.day.month == today.month),
        minutes_this_week=sum(w.minutes for w in workouts if w.day >= this_week),
        current_week_streak=workout_streak_weeks(workouts, weekly_goal, today),
        best_week_streak=best_week_streak(workouts, weekly_goal),
        best_day_streak=longest_run(days, lambda prev, cur: cur - prev == timedelta(days=1)),
        favorite_activity=Counter(w.activity for w in workouts).most_common(1)[0][0],
    )
