from datetime import date, timedelta

from fitflow.domain.insights import (
    generate_insights, protein_on_training_days, week_start, weekend_overeating,
    weekly_workout_counts, workout_streak_weeks,
)
from fitflow.domain.models import DaySummary, Macros, Workout, WorkoutCategory

SUNDAY = date(2026, 9, 6)
TARGET = Macros(2200, 160, 230, 60)


def run(day: date, category=WorkoutCategory.STRENGTH) -> Workout:
    return Workout(day, "strength_training", category, 60, 300)


def summary(day: date, kcal: float, protein: float = 160, trained: bool = False) -> DaySummary:
    return DaySummary(day, Macros(kcal, protein, 200, 60), TARGET, (run(day),) if trained else ())


def four_weeks(by_weekday: dict[int, dict]) -> list[DaySummary]:
    """28 days on target, except weekdays listed in by_weekday (Python weekday: Monday=0)."""
    days = [SUNDAY + timedelta(days=n) for n in range(28)]
    return [summary(d, **by_weekday.get(d.weekday(), {"kcal": 2200})) for d in days]


def test_week_starts_on_sunday():
    assert week_start(date(2026, 9, 10)) == SUNDAY   # Thursday
    assert week_start(SUNDAY) == SUNDAY


def test_weekly_counts_by_category():
    workouts = [run(SUNDAY), run(SUNDAY + timedelta(days=2), WorkoutCategory.CARDIO),
                run(SUNDAY + timedelta(days=7))]  # next week - not counted
    counts = weekly_workout_counts(workouts, SUNDAY + timedelta(days=3))
    assert counts == {WorkoutCategory.STRENGTH: 1, WorkoutCategory.CARDIO: 1, WorkoutCategory.OTHER: 0}


def test_streak_counts_consecutive_weeks():
    workouts = [run(SUNDAY + timedelta(days=7 * w + d)) for w in range(3) for d in (0, 2, 4)]
    today = SUNDAY + timedelta(days=15)
    assert workout_streak_weeks(workouts, weekly_goal=3, today=today) == 3


def test_unfinished_current_week_does_not_break_streak():
    workouts = [run(SUNDAY + timedelta(days=7 * w + d)) for w in range(2) for d in (0, 2, 4)]
    today = SUNDAY + timedelta(days=14)  # third week just started, no workouts yet
    assert workout_streak_weeks(workouts, weekly_goal=3, today=today) == 2


def test_detects_weekend_overeating():
    days = four_weeks({4: {"kcal": 2700}, 5: {"kcal": 2700}})  # Fri, Sat
    insight = weekend_overeating(days)
    assert insight is not None and insight.data["kcal_gap"] == 500


def test_small_weekend_difference_is_not_reported():
    days = four_weeks({4: {"kcal": 2300}, 5: {"kcal": 2300}})
    assert weekend_overeating(days) is None


def test_not_enough_data_is_not_reported():
    days = four_weeks({4: {"kcal": 2700}, 5: {"kcal": 2700}})[:7]
    assert weekend_overeating(days) is None


def test_detects_protein_gap_on_rest_days():
    trained = {"kcal": 2200, "trained": True}
    low_protein = {"kcal": 2200, "protein": 100}
    days = four_weeks({0: trained, 2: trained} | {d: low_protein for d in (1, 3, 4, 5, 6)})
    insight = protein_on_training_days(days)
    assert insight is not None and insight.data == {"training_rate": 1.0, "rest_rate": 0.0}


def test_generate_insights_skips_empty_ones():
    assert generate_insights([], [], weekly_goal=3, today=SUNDAY) == []
