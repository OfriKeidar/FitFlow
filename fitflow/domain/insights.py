"""Pattern detection over the user's history.

Every insight is plain statistics computed here. An insight is only reported when there is
enough data AND the effect is big enough to matter - otherwise we'd be showing noise.
The AI layer may rephrase the message, but never invents the numbers.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean

from fitflow.domain.models import DaySummary, Workout, WorkoutCategory

WEEKEND = {4, 5}  # Friday, Saturday (Israeli week). Python: Monday=0 ... Sunday=6

MIN_WEEKEND_DAYS = 4
MIN_WEEKDAYS = 8
MIN_KCAL_GAP = 200         # weekend effect must be at least this big to report

PROTEIN_HIT_SHARE = 0.9    # "hit protein" = ate at least 90% of the protein target
MIN_DAYS_PER_GROUP = 4
MIN_HIT_RATE_GAP = 0.2     # 20 percentage points


@dataclass(frozen=True)
class Insight:
    kind: str
    message: str
    data: dict = field(default_factory=dict)


def week_start(d: date) -> date:
    """Sunday on or before d (the Israeli week starts on Sunday)."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def weekly_workout_counts(workouts: list[Workout], week_of: date) -> dict[WorkoutCategory, int]:
    start = week_start(week_of)
    counts = {c: 0 for c in WorkoutCategory}
    for w in workouts:
        if start <= w.day < start + timedelta(days=7):
            counts[w.category] += 1
    return counts


def workout_streak_weeks(workouts: list[Workout], weekly_goal: int, today: date) -> int:
    """Consecutive weeks (ending now) in which the weekly workout goal was reached.

    The current week counts only once the goal is already met - an unfinished week
    shouldn't break the streak.
    """
    def met(week: date) -> bool:
        return sum(weekly_workout_counts(workouts, week).values()) >= weekly_goal

    week = week_start(today)
    streak = 1 if met(week) else 0
    week -= timedelta(days=7)
    while met(week):
        streak += 1
        week -= timedelta(days=7)
    return streak


def weekend_overeating(days: list[DaySummary]) -> Insight | None:
    weekend = [d.intake.kcal - d.target.kcal for d in days if d.day.weekday() in WEEKEND]
    weekdays = [d.intake.kcal - d.target.kcal for d in days if d.day.weekday() not in WEEKEND]
    if len(weekend) < MIN_WEEKEND_DAYS or len(weekdays) < MIN_WEEKDAYS:
        return None

    gap = mean(weekend) - mean(weekdays)
    if abs(gap) < MIN_KCAL_GAP:
        return None
    direction = "מעל" if gap > 0 else "מתחת ל"
    return Insight(
        "weekend_kcal",
        f"בסופי שבוע אתה אוכל בממוצע {abs(gap):.0f} קק\"ל {direction}ימי החול",
        {"kcal_gap": round(gap)},
    )


def protein_on_training_days(days: list[DaySummary]) -> Insight | None:
    def hit_rate(group: list[DaySummary]) -> float:
        return mean(d.intake.protein_g >= PROTEIN_HIT_SHARE * d.target.protein_g for d in group)

    training = [d for d in days if d.workouts]
    rest = [d for d in days if not d.workouts]
    if len(training) < MIN_DAYS_PER_GROUP or len(rest) < MIN_DAYS_PER_GROUP:
        return None

    train_rate, rest_rate = hit_rate(training), hit_rate(rest)
    if abs(train_rate - rest_rate) < MIN_HIT_RATE_GAP:
        return None
    return Insight(
        "protein_training",
        # Hebrew maqaf (U+05BE), not "-": an ASCII hyphen before a number breaks right-to-left display.
        f"בימי אימון עמדת ביעד החלבון ב־{train_rate:.0%} מהימים, בימי מנוחה ב־{rest_rate:.0%}",
        {"training_rate": round(train_rate, 2), "rest_rate": round(rest_rate, 2)},
    )


def workout_streak(workouts: list[Workout], weekly_goal: int, today: date) -> Insight | None:
    streak = workout_streak_weeks(workouts, weekly_goal, today)
    if streak < 2:
        return None
    return Insight(
        "workout_streak",
        f"רצף של {streak} שבועות עם {weekly_goal} אימונים ומעלה",
        {"weeks": streak},
    )


def generate_insights(
    days: list[DaySummary], workouts: list[Workout], weekly_goal: int, today: date
) -> list[Insight]:
    candidates = [
        weekend_overeating(days),
        protein_on_training_days(days),
        workout_streak(workouts, weekly_goal, today),
    ]
    return [i for i in candidates if i is not None]
