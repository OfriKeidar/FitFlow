"""Initial energy and macro targets, computed from the user's profile.

These are population formulas - a starting guess. `trend.py` later replaces the
guess with the user's real expenditure, learned from their own data.
"""

from fitflow.domain.models import KCAL_PER_KG, Goal, Macros, Profile, Sex

# Safety limits
MAX_CUT_RATE_PCT = 0.01    # lose at most 1% of body weight per week
MAX_BULK_RATE_PCT = 0.005  # gain at most 0.5% of body weight per week
MIN_KCAL = {Sex.MALE: 1500, Sex.FEMALE: 1200}

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


def safe_weekly_rate(profile: Profile) -> float:
    """The requested weekly rate, capped to a safe percentage of body weight."""
    if profile.goal == Goal.CUT:
        return min(profile.weekly_rate_kg, profile.weight_kg * MAX_CUT_RATE_PCT)
    if profile.goal == Goal.BULK:
        return min(profile.weekly_rate_kg, profile.weight_kg * MAX_BULK_RATE_PCT)
    return 0.0


def daily_calorie_target(profile: Profile, tdee: float) -> float:
    """TDEE +/- the daily energy gap needed to hit the weekly rate."""
    daily_gap = safe_weekly_rate(profile) * KCAL_PER_KG / 7
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
