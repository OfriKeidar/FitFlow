"""Calories burned by workouts, using MET values.

MET = how many times more energy an activity uses compared to sitting still.
Source: Compendium of Physical Activities (approximate values).
"""

MET = {
    "walking": 3.5,
    "brisk_walking": 4.3,
    "running": 9.8,
    "cycling": 7.5,
    "swimming": 7.0,
    "strength_training": 5.0,
    "hiit": 8.0,
    "yoga": 2.5,
    "football": 7.0,
    "basketball": 6.5,
}


def workout_kcal(activity: str, minutes: float, weight_kg: float) -> float:
    """NET calories burned: we subtract 1 MET because resting burn is already in the TDEE.

    Without this, a 1-hour walk would be counted twice - once in BMR, once here.
    """
    if activity not in MET:
        raise ValueError(f"Unknown activity: {activity!r}. Known: {sorted(MET)}")
    return (MET[activity] - 1) * weight_kg * minutes / 60
