from datetime import date, timedelta

from fitflow.domain.models import Workout, WorkoutCategory
from fitflow.domain.workout_stats import workout_stats

SUNDAY = date(2026, 9, 6)


def w(day: date, activity: str = "running", minutes: float = 30) -> Workout:
    return Workout(day, activity, WorkoutCategory.CARDIO, minutes, 200)


def test_no_workouts():
    stats = workout_stats([], weekly_goal=3, today=SUNDAY)
    assert stats.total_workouts == 0 and stats.days_since_last is None and stats.favorite_activity is None


def test_days_since_last_and_favorite():
    workouts = [w(SUNDAY), w(SUNDAY + timedelta(days=1), "yoga"), w(SUNDAY + timedelta(days=2))]
    stats = workout_stats(workouts, weekly_goal=3, today=SUNDAY + timedelta(days=5))
    assert stats.days_since_last == 3
    assert stats.favorite_activity == "running"
    assert stats.best_day_streak == 3
    assert stats.minutes_this_week == 90


def test_best_week_streak_counts_the_longest_run_of_good_weeks():
    good = lambda week: [w(SUNDAY + timedelta(days=7 * week + d)) for d in (0, 2, 4)]  # noqa: E731
    bad = lambda week: [w(SUNDAY + timedelta(days=7 * week))]  # noqa: E731
    # weeks: good, good, good, bad, good
    workouts = good(0) + good(1) + good(2) + bad(3) + good(4)
    stats = workout_stats(workouts, weekly_goal=3, today=SUNDAY + timedelta(days=7 * 4 + 5))
    assert stats.best_week_streak == 3
    assert stats.current_week_streak == 1


def test_this_month_only_counts_the_current_month():
    workouts = [w(date(2026, 8, 30)), w(date(2026, 9, 1)), w(date(2026, 9, 10))]
    assert workout_stats(workouts, weekly_goal=3, today=date(2026, 9, 20)).this_month == 2
