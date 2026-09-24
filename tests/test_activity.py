import pytest

from fitflow.domain.activity import workout_kcal


def test_net_kcal_subtracts_resting_met():
    # running: (9.8 - 1) * 80 kg * 0.5 h = 352
    assert workout_kcal("running", minutes=30, weight_kg=80) == pytest.approx(352)


def test_unknown_activity_raises():
    with pytest.raises(ValueError):
        workout_kcal("underwater_chess", 30, 80)
