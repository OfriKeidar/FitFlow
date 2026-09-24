import random
from datetime import date, timedelta

import pytest

from fitflow.domain.models import KCAL_PER_KG, WeighIn
from fitflow.domain.trend import MAX_STEP_KCAL, adaptive_tdee, weight_trend

START = date(2026, 1, 1)


def day(n: int) -> date:
    return START + timedelta(days=n)


def simulate(true_tdee: float, intake: float, days: int, every: int, noise: float = 0.0, seed: int = 1):
    """A fake user whose weight changes exactly by energy balance, plus scale noise."""
    rng = random.Random(seed)
    weight, weigh_ins = 80.0, []
    for n in range(days + 1):
        if n % every == 0:
            weigh_ins.append(WeighIn(day(n), weight + rng.uniform(-noise, noise)))
        weight += (intake - true_tdee) / KCAL_PER_KG
    intake_by_day = {day(n): intake for n in range(days)}
    return weigh_ins, intake_by_day


def test_trend_smooths_noise():
    readings = [WeighIn(day(n), 80 + (1 if n % 2 else -1)) for n in range(30)]  # jumps +/-1 kg daily
    trend = weight_trend(readings)
    assert max(t.weight_kg for t in trend[10:]) - min(t.weight_kg for t in trend[10:]) < 0.5


def test_trend_trusts_readings_more_when_weighing_rarely():
    daily = weight_trend([WeighIn(day(0), 80), WeighIn(day(1), 82)])
    monthly = weight_trend([WeighIn(day(0), 80), WeighIn(day(30), 82)])
    assert monthly[-1].weight_kg > daily[-1].weight_kg


def test_not_enough_days_keeps_previous_estimate():
    weigh_ins, intake = simulate(true_tdee=2500, intake=2000, days=7, every=1)
    result = adaptive_tdee(2300, weigh_ins, intake, {})
    assert result.tdee == 2300 and result.observed is None


def test_too_few_logged_days_keeps_previous_estimate():
    weigh_ins, intake = simulate(true_tdee=2500, intake=2000, days=28, every=7)
    sparse = dict(list(intake.items())[:10])
    assert adaptive_tdee(2300, weigh_ins, sparse, {}).observed is None


@pytest.mark.parametrize("every", [1, 7, 30])
def test_learns_true_tdee_for_any_weigh_in_frequency(every):
    weigh_ins, intake = simulate(true_tdee=2600, intake=2100, days=60, every=every)
    result = adaptive_tdee(2600, weigh_ins, intake, {})
    assert result.observed == pytest.approx(2600, abs=150)


def test_update_step_is_capped():
    weigh_ins, intake = simulate(true_tdee=3000, intake=2000, days=28, every=1)
    result = adaptive_tdee(2000, weigh_ins, intake, {})
    assert result.tdee == 2000 + MAX_STEP_KCAL


def test_workout_calories_are_excluded_from_baseline():
    weigh_ins, intake = simulate(true_tdee=2600, intake=2600, days=28, every=1)  # weight stable
    workouts = {d: 300 for d in intake}
    result = adaptive_tdee(2300, weigh_ins, intake, workouts)
    assert result.observed == pytest.approx(2300, abs=1)


def test_slope_is_exact_on_a_straight_line():
    from fitflow.domain.trend import weight_slope
    readings = [WeighIn(day(n), 80 - 0.1 * n) for n in range(0, 22, 7)]
    assert weight_slope(readings) == pytest.approx(-0.1)


def test_exact_with_few_weekly_weigh_ins():
    """Regression: EWMA-based change lagged here and underestimated TDEE by ~150 kcal."""
    weigh_ins, intake = simulate(true_tdee=2550, intake=2000, days=21, every=7)
    assert adaptive_tdee(2550, weigh_ins, intake, {}).observed == pytest.approx(2550, abs=1)


def test_noisy_daily_weigh_ins_still_converge():
    weigh_ins, intake = simulate(true_tdee=2600, intake=2100, days=28, every=1, noise=1.0)
    assert adaptive_tdee(2600, weigh_ins, intake, {}).observed == pytest.approx(2600, abs=200)
