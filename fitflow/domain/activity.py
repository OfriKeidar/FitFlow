"""Calories burned by workouts, using MET values.

MET = how many times more energy an activity uses compared to sitting still.
Source: Compendium of Physical Activities (approximate values).
"""

from dataclasses import dataclass

from fitflow.domain.models import WorkoutCategory


@dataclass(frozen=True)
class Activity:
    met: float
    category: WorkoutCategory


ACTIVITIES = {
    "strength_training": Activity(5.0, WorkoutCategory.STRENGTH),
    "crossfit": Activity(8.0, WorkoutCategory.STRENGTH),
    "walking": Activity(3.5, WorkoutCategory.CARDIO),
    "brisk_walking": Activity(4.3, WorkoutCategory.CARDIO),
    "running": Activity(9.8, WorkoutCategory.CARDIO),
    "cycling": Activity(7.5, WorkoutCategory.CARDIO),
    "swimming": Activity(7.0, WorkoutCategory.CARDIO),
    "hiit": Activity(8.0, WorkoutCategory.CARDIO),
    "yoga": Activity(2.5, WorkoutCategory.OTHER),
    "pilates": Activity(3.0, WorkoutCategory.OTHER),
    "football": Activity(7.0, WorkoutCategory.OTHER),
    "basketball": Activity(6.5, WorkoutCategory.OTHER),
    "other": Activity(4.5, WorkoutCategory.OTHER),  # anything else (e.g. unknown types synced from a watch)
}

# Workout types as Health Connect / HealthKit name them (via the Capacitor plugin) -> our activities.
# Keys are normalized: lowercase, no spaces or underscores.
HEALTH_WORKOUT_TYPES = {
    "running": "running", "runningtreadmill": "running",
    "walking": "walking", "hiking": "walking",
    "cycling": "cycling", "handcycling": "cycling", "bikingstationary": "cycling",
    "swimming": "swimming", "swimmingpool": "swimming", "swimmingopenwater": "swimming",
    "strengthtraining": "strength_training", "traditionalstrengthtraining": "strength_training",
    "functionalstrengthtraining": "strength_training", "weightlifting": "strength_training",
    "crosstraining": "crossfit",
    "highintensityintervaltraining": "hiit",
    "yoga": "yoga", "pilates": "pilates",
    "soccer": "football", "basketball": "basketball",
}


def activity_for_health_type(workout_type: str) -> str:
    """Map a phone/watch workout type to one of ours; unknown types become "other"."""
    key = workout_type.lower().replace(" ", "").replace("_", "")
    return HEALTH_WORKOUT_TYPES.get(key, "other")


def get_activity(name: str) -> Activity:
    if name not in ACTIVITIES:
        raise ValueError(f"Unknown activity: {name!r}. Known: {sorted(ACTIVITIES)}")
    return ACTIVITIES[name]


def workout_kcal(activity: str, minutes: float, weight_kg: float) -> float:
    """NET calories burned: we subtract 1 MET because resting burn is already in the TDEE.

    Without this, a 1-hour walk would be counted twice - once in BMR, once here.
    """
    return (get_activity(activity).met - 1) * weight_kg * minutes / 60
