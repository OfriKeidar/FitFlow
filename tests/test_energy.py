import pytest

from fitflow.domain.energy import (
    bmr, daily_calorie_target, daily_targets, initial_tdee, weekly_rate_kg, weeks_to_target,
)
from fitflow.domain.models import ActivityLevel, Experience, Goal, Pace, Profile, Sex


def make_profile(**overrides) -> Profile:
    defaults = dict(
        sex=Sex.MALE, age=25, height_cm=180, weight_kg=80,
        activity=ActivityLevel.SEDENTARY, goal=Goal.CUT, target_weight_kg=72, pace=Pace.RECOMMENDED,
    )
    return Profile(**(defaults | overrides))


def test_bmr_mifflin_male():
    # 10*80 + 6.25*180 - 5*25 + 5 = 1805
    assert bmr(make_profile()) == pytest.approx(1805)


def test_bmr_female_is_lower_by_166():
    assert bmr(make_profile()) - bmr(make_profile(sex=Sex.FEMALE)) == pytest.approx(166)


def test_tdee_applies_activity_factor():
    assert initial_tdee(make_profile()) == pytest.approx(1805 * 1.2)


def test_pace_is_a_share_of_body_weight():
    assert weekly_rate_kg(make_profile()) == pytest.approx(0.6)                 # 0.75% of 80 kg
    assert weekly_rate_kg(make_profile(pace=Pace.FAST)) == pytest.approx(0.8)   # 1% of 80 kg


def test_cut_creates_deficit_from_weekly_rate():
    # 0.6 kg/week * 7700 / 7 = 660 kcal/day
    assert daily_calorie_target(make_profile(), tdee=2500) == pytest.approx(1840)


def test_weeks_to_target():
    assert weeks_to_target(make_profile()) == 14  # 8 kg / 0.6 kg per week = 13.3 -> 14


def test_reaching_the_target_switches_to_maintenance():
    at_target = make_profile(weight_kg=71.5)
    assert weekly_rate_kg(at_target) == 0
    assert daily_calorie_target(at_target, tdee=2500) == 2500
    assert weeks_to_target(at_target) is None


def test_cut_never_goes_below_minimum_calories():
    assert daily_calorie_target(make_profile(), tdee=1600) == 1500


def test_maintain_ignores_weekly_rate():
    assert daily_calorie_target(make_profile(goal=Goal.MAINTAIN, target_weight_kg=None), tdee=2500) == 2500


def test_macros_add_up_to_calories():
    t = daily_targets(make_profile(), tdee=2500)
    assert t.protein_g == pytest.approx(2.2 * 80)
    assert t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9 == pytest.approx(t.kcal)


def test_workout_calories_raise_todays_target():
    base = daily_targets(make_profile(), tdee=2500)
    with_workout = daily_targets(make_profile(), tdee=2500, workout_kcal=300)
    assert with_workout.kcal - base.kcal == pytest.approx(300)



def test_bulk_pace_depends_on_training_experience():
    # Beginners build muscle fastest, so they may gain faster without most of it being fat.
    bulk = dict(goal=Goal.BULK, target_weight_kg=90)
    rates = [weekly_rate_kg(make_profile(**bulk, experience=e))
             for e in (Experience.BEGINNER, Experience.INTERMEDIATE, Experience.ADVANCED)]
    assert rates == pytest.approx([0.28, 0.2, 0.12])  # 0.35%, 0.25%, 0.15% of 80 kg
    # The cut rate doesn't depend on experience.
    assert weekly_rate_kg(make_profile(experience=Experience.BEGINNER)) == weekly_rate_kg(make_profile())
