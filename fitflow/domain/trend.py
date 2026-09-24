"""Weight trend smoothing and adaptive TDEE - the system "learns" the user's metabolism.

Idea: if you ate X kcal/day on average and your weight changed by Y kg/day,
then your real expenditure was X - Y * 7700. No formula guessing needed.

Two tools, two jobs:
  - EWMA trend (weight_trend): smooth line for the progress chart.
  - Linear regression slope (weight_slope): the rate of change used for the TDEE math.
    EWMA lags behind a steady trend, which would systematically underestimate the change;
    a least-squares slope has no lag and still averages out the noise.
"""

from dataclasses import dataclass
from datetime import date

from fitflow.domain.models import KCAL_PER_KG, WeighIn

DAILY_ALPHA = 0.1          # how much a single day's weigh-in moves the trend
MIN_DAYS = 14              # don't adapt before we have two weeks of data
MIN_LOGGED_SHARE = 0.7     # need food logged on at least 70% of days
LEARNING_RATE = 0.5        # move halfway from the old estimate towards the new observation
MAX_STEP_KCAL = 150        # never move the TDEE by more than this in a single update


def weight_trend(weigh_ins: list[WeighIn]) -> list[WeighIn]:
    """Time-aware exponential moving average (EWMA).

    Water and salt make the scale jump +/-1 kg day to day. The trend filters that noise.
    Because users weigh in daily, weekly OR monthly, alpha depends on the gap between
    weigh-ins: after 1 day we trust the new reading 10%, after 7 days ~52%, after 30 ~96%.
    """
    points = sorted(weigh_ins, key=lambda w: w.day)
    if not points:
        return []

    trend = [points[0]]
    for prev, cur in zip(points, points[1:]):
        gap_days = (cur.day - prev.day).days
        alpha = 1 - (1 - DAILY_ALPHA) ** gap_days
        smoothed = trend[-1].weight_kg + alpha * (cur.weight_kg - trend[-1].weight_kg)
        trend.append(WeighIn(cur.day, smoothed))
    return trend


def weight_slope(weigh_ins: list[WeighIn]) -> float:
    """Least-squares slope in kg/day: the straight line that best fits all readings."""
    origin = min(w.day for w in weigh_ins)
    xs = [(w.day - origin).days for w in weigh_ins]
    ys = [w.weight_kg for w in weigh_ins]
    x_mean, y_mean = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    return numerator / denominator


@dataclass(frozen=True)
class TdeeUpdate:
    tdee: float                 # the estimate to use from now on
    observed: float | None      # what the data alone says (None if not enough data)
    reason: str


def adaptive_tdee(
    previous_tdee: float,
    weigh_ins: list[WeighIn],
    intake_by_day: dict[date, float],
    workout_by_day: dict[date, float],
) -> TdeeUpdate:
    """Re-estimate baseline TDEE (excluding workouts) from real intake and weight change."""
    points = sorted(weigh_ins, key=lambda w: w.day)
    if len(points) < 2:
        return TdeeUpdate(previous_tdee, None, "need at least 2 weigh-ins")

    start, end = points[0].day, points[-1].day
    days = (end - start).days
    if days < MIN_DAYS:
        return TdeeUpdate(previous_tdee, None, f"need {MIN_DAYS} days of data, have {days}")

    logged = [d for d in intake_by_day if start <= d < end]
    if len(logged) < days * MIN_LOGGED_SHARE:
        return TdeeUpdate(previous_tdee, None, f"food logged on only {len(logged)}/{days} days")

    avg_intake = sum(intake_by_day[d] for d in logged) / len(logged)
    avg_workout = sum(workout_by_day.get(d, 0) for d in logged) / len(logged)
    stored_per_day = weight_slope(points) * KCAL_PER_KG

    # Energy balance: intake = expenditure + stored  =>  expenditure = intake - stored
    observed = avg_intake - stored_per_day - avg_workout

    step = LEARNING_RATE * (observed - previous_tdee)
    step = max(-MAX_STEP_KCAL, min(MAX_STEP_KCAL, step))
    return TdeeUpdate(previous_tdee + step, observed, "updated from your data")
