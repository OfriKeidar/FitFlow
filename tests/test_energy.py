import pytest

from fitflow.domain.energy import bmr, daily_calorie_target, daily_targets, initial_tdee, safe_weekly_rate
from fitflow.domain.models import ActivityLevel, Goal, Profile, Sex


def make_profile(**overrides) -> Profile:
    defaults = dict(
        sex=Sex.MALE, age=25, height_cm=180, weight_kg=80,
        activity=ActivityLevel.SEDENTARY, goal=Goal.CUT, weekly_rate_kg=0.5,
    )
    return Profile(**(defaults | overrides))


def test_bmr_mifflin_male():
    # 10*80 + 6.25*180 - 5*25 + 5 = 1805
    assert bmr(make_profile()) == pytest.approx(1805)


def test_bmr_female_is_lower_by_166():
    assert bmr(make_profile()) - bmr(make_profile(sex=Sex.FEMALE)) == pytest.approx(166)


def test_tdee_applies_activity_factor():
    assert initial_tdee(make_profile()) == pytest.approx(1805 * 1.2)


def test_cut_creates_deficit_from_weekly_rate():
    # 0.5 kg/week * 7700 / 7 = 550 kcal/day
    assert daily_calorie_target(make_profile(), tdee=2500) == pytest.approx(1950)


def test_unsafe_cut_rate_is_capped_to_1_percent():
    assert safe_weekly_rate(make_profile(weekly_rate_kg=2.0)) == pytest.approx(0.8)


def test_cut_never_goes_below_minimum_calories():
    assert daily_calorie_target(make_profile(), tdee=1600) == 1500


def test_maintain_ignores_weekly_rate():
    assert daily_calorie_target(make_profile(goal=Goal.MAINTAIN), tdee=2500) == 2500


def test_macros_add_up_to_calories():
    t = daily_targets(make_profile(), tdee=2500)
    assert t.protein_g == pytest.approx(2.2 * 80)
    assert t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9 == pytest.approx(t.kcal)


def test_workout_calories_raise_todays_target():
    base = daily_targets(make_profile(), tdee=2500)
    with_workout = daily_targets(make_profile(), tdee=2500, workout_kcal=300)
    assert with_workout.kcal - base.kcal == pytest.approx(300)
