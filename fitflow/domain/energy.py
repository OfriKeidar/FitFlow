"""Initial energy and macro targets, computed from the user's profile.

These are population formulas - a starting guess. `trend.py` later replaces the
guess with the user's real expenditure, learned from their own data.
"""

import math

from fitflow.domain.models import KCAL_PER_KG, Experience, Goal, Macros, Pace, Profile, Sex

# Weekly weight change as a share of body weight. Percentages (not fixed kg) keep the pace
# safe for every body size.
# Cut: 0.5-1%/week is the usual range for losing fat while keeping muscle (Helms et al., 2014).
CUT_RATE_PCT = {Pace.RELAXED: 0.005, Pace.RECOMMENDED: 0.0075, Pace.FAST: 0.01}
# Bulk: muscle can only be built so fast, and a bigger surplus mostly adds fat. How fast depends on
# training experience - beginners gain muscle fastest (roughly 1-2% of body weight a month, falling to
# ~0.5% for advanced lifters; Iraki et al., 2019). "Fast" for a beginner fits "hard gainers" too.
BULK_RATE_PCT = {
    Experience.BEGINNER: {Pace.RELAXED: 0.0025, Pace.RECOMMENDED: 0.0035, Pace.FAST: 0.005},
    Experience.INTERMEDIATE: {Pace.RELAXED: 0.0015, Pace.RECOMMENDED: 0.0025, Pace.FAST: 0.004},
    Experience.ADVANCED: {Pace.RELAXED: 0.001, Pace.RECOMMENDED: 0.0015, Pace.FAST: 0.0025},
}
MIN_KCAL = {Sex.MALE: 1500, Sex.FEMALE: 1200}  # safety floor

PROTEIN_G_PER_KG = {Goal.CUT: 2.2, Goal.MAINTAIN: 1.8, Goal.BULK: 1.8}
FAT_SHARE = 0.25  # 25% of calories from fat; carbs fill the rest
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9


def bmr(profile: Profile) -> float:
    """Basal metabolic rate (Mifflin-St Jeor): calories burned at complete rest."""
    base = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age
    return base + 5 if profile.sex == Sex.MALE else base - 161


def initial_tdee(profile: Profile) -> float:
    """Total daily energy expenditure, excluding logged workouts."""
    return bmr(profile) * profile.activity.value


def target_reached(profile: Profile) -> bool:
    """Cutting and already at/below the target, or bulking and already at/above it."""
    if profile.target_weight_kg is None:
        return False
    if profile.goal == Goal.CUT:
        return profile.weight_kg <= profile.target_weight_kg
    if profile.goal == Goal.BULK:
        return profile.weight_kg >= profile.target_weight_kg
    return False


def weekly_rate_kg(profile: Profile) -> float:
    """How many kg per week to lose or gain (always positive). 0 when maintaining or at target."""
    if profile.goal == Goal.MAINTAIN or target_reached(profile):
        return 0.0
    if profile.goal == Goal.CUT:
        return profile.weight_kg * CUT_RATE_PCT[profile.pace]
    return profile.weight_kg * BULK_RATE_PCT[profile.experience][profile.pace]


def weeks_to_target(profile: Profile) -> int | None:
    """Estimated weeks until the target weight, or None if there is no target to move towards."""
    rate = weekly_rate_kg(profile)
    if rate == 0 or profile.target_weight_kg is None:
        return None
    return math.ceil(abs(profile.weight_kg - profile.target_weight_kg) / rate)


def daily_calorie_target(profile: Profile, tdee: float) -> float:
    """TDEE +/- the daily energy gap needed for the weekly rate. At the target, it's maintenance."""
    daily_gap = weekly_rate_kg(profile) * KCAL_PER_KG / 7
    if profile.goal == Goal.CUT:
        return max(tdee - daily_gap, MIN_KCAL[profile.sex])
    if profile.goal == Goal.BULK:
        return tdee + daily_gap
    return tdee


def macro_targets(profile: Profile, kcal: float) -> Macros:
    """Protein by body weight, fat by share of calories, carbs = whatever is left."""
    protein_g = PROTEIN_G_PER_KG[profile.goal] * profile.weight_kg
    fat_g = kcal * FAT_SHARE / KCAL_PER_G_FAT
    carbs_kcal = kcal - protein_g * KCAL_PER_G_PROTEIN - fat_g * KCAL_PER_G_FAT
    carbs_g = max(carbs_kcal, 0) / KCAL_PER_G_CARB
    return Macros(kcal=kcal, protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g)


def daily_targets(profile: Profile, tdee: float, workout_kcal: float = 0.0) -> Macros:
    """Today's targets. Workout calories are "earned" on top of the base target."""
    return macro_targets(profile, daily_calorie_target(profile, tdee) + workout_kcal)
