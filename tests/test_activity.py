import pytest

from fitflow.domain.activity import workout_kcal


def test_net_kcal_subtracts_resting_met():
    # running: (9.8 - 1) * 80 kg * 0.5 h = 352
    assert workout_kcal("running", minutes=30, weight_kg=80) == pytest.approx(352)


def test_unknown_activity_raises():
    with pytest.raises(ValueError):
        workout_kcal("underwater_chess", 30, 80)


def test_activities_have_categories():
    from fitflow.domain.activity import get_activity
    from fitflow.domain.models import WorkoutCategory
    assert get_activity("strength_training").category == WorkoutCategory.STRENGTH
    assert get_activity("running").category == WorkoutCategory.CARDIO
