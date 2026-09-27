"""Meal suggestion from what the user has at home, as an Integer Linear Program (ILP).

Decision variables
    servings[f]  integer  how many servings of food f to eat (0..max_servings)
    used[f]      binary   1 if food f is in the meal at all

Constraints ("a meal that makes sense")
    - only foods that fit this meal (no cereal for dinner) and aren't disliked
    - at most MAX_ITEMS different foods in the meal
    - at most MAX_PER_CATEGORY foods from the same category (not 3 kinds of carbs)

Objective
    minimize the (normalized) distance from the macros the user still needs,
    where missing protein and exceeding calories are penalized the most.

Two uses of the same model:
    suggest_meal  the solver picks the foods (from the pantry) and the amounts
    fit_meal      the user picks the foods ("I'm thinking of...") and the solver picks the amounts
"""

from dataclasses import dataclass

import pulp

from fitflow.domain.models import Food, FoodCategory, Macros, Meal, PantryItem, ZERO_MACROS

MAX_ITEMS = 4
MAX_PER_CATEGORY = 2
PER_ITEM_PENALTY = 0.02  # small nudge towards simpler meals

# (penalty for being under target, penalty for being over target)
WEIGHTS = {
    "kcal": (1.0, 3.0),       # going over calories is bad
    "protein_g": (4.0, 0.3),  # missing protein is the worst; extra protein is fine
    "carbs_g": (0.5, 0.5),
    "fat_g": (0.5, 1.0),
}


def meal_for_hour(hour: int) -> Meal:
    """Users log one flat list per day, so we infer what kind of meal makes sense from the clock."""
    if 5 <= hour < 11:
        return Meal.BREAKFAST
    if 11 <= hour < 16:
        return Meal.LUNCH
    if 16 <= hour < 18:
        return Meal.SNACK
    return Meal.DINNER


# How many meals are usually still ahead (including this one) at each point in the day.
MEALS_LEFT = {Meal.BREAKFAST: 4, Meal.LUNCH: 3, Meal.SNACK: 2, Meal.DINNER: 1}
MAX_MEAL_SHARE = 0.4  # one meal is at most 40% of the whole day's calories


def meal_target(remaining: Macros, daily_target: Macros, meal: Meal) -> Macros:
    """What THIS meal should cover: an even share of what's left today, capped to a sane size.

    Without this, at breakfast the optimizer would try to fit the whole day into one plate.
    """
    share = remaining.scale(1 / MEALS_LEFT[meal])
    cap = daily_target.kcal * MAX_MEAL_SHARE
    if share.kcal > cap:
        share = share.scale(cap / share.kcal)  # shrink all macros proportionally
    return share


@dataclass(frozen=True)
class MealSuggestion:
    items: list[tuple[PantryItem, float]]  # (pantry item, servings)
    totals: Macros


def suggest_meal(
    pantry: list[PantryItem],
    target: Macros,
    meal: Meal,
    disliked: frozenset[str] = frozenset(),
    exclude: list[frozenset[str]] = (),
) -> MealSuggestion:
    """The best meal from what's at home.

    `exclude`: food combinations already suggested - "give me a different suggestion" adds the
    current one here, and the solver must find the next-best combination.
    """
    candidates = [
        p for p in pantry
        if meal in p.food.meals and p.food.name not in disliked and p.max_servings > 0
    ]
    if not candidates or target.kcal <= 0:
        return MealSuggestion([], ZERO_MACROS)
    return _solve(candidates, target, step=1.0, must_use_all=False, exclude=exclude)


FIT_MAX_SERVINGS = 6  # upper bound per food when fitting the user's own meal idea
FIT_STEP = 0.5        # half servings: more precise amounts (e.g. 150 g instead of 100 or 200)


def fit_meal(foods: list[Food], target: Macros) -> MealSuggestion:
    """"I'm thinking of eating chicken, rice and salad" -> how much of each fits what I have left.

    Same model as suggest_meal, but every chosen food must be in the meal (at least half a serving),
    and there are no pantry limits or meal-structure rules - the user already decided what to eat.
    """
    if not foods or target.kcal <= 0:
        return MealSuggestion([], ZERO_MACROS)
    candidates = [PantryItem(food, FIT_MAX_SERVINGS) for food in foods]
    return _solve(candidates, target, step=FIT_STEP, must_use_all=True, exclude=())


def _solve(
    candidates: list[PantryItem], target: Macros, step: float, must_use_all: bool,
    exclude: list[frozenset[str]],
) -> MealSuggestion:
    prob = pulp.LpProblem("meal", pulp.LpMinimize)
    # units[i] = how many `step`-sized portions of food i (e.g. step 0.5 -> 3 units = 1.5 servings)
    units = {
        i: prob.add_variable(f"units_{i}", 0, round(p.max_servings / step), cat="Integer")
        for i, p in enumerate(candidates)
    }
    used = {i: prob.add_variable(f"used_{i}", cat="Binary") for i in units}

    # Link the two variables: units > 0  <=>  used = 1
    for i, p in enumerate(candidates):
        prob += units[i] <= round(p.max_servings / step) * used[i]
        prob += units[i] >= used[i]
        if must_use_all:
            prob += used[i] == 1

    if not must_use_all:
        prob += pulp.lpSum(used.values()) <= MAX_ITEMS
        for category in FoodCategory:
            in_category = [used[i] for i, p in enumerate(candidates) if p.food.category == category]
            if in_category:
                prob += pulp.lpSum(in_category) <= MAX_PER_CATEGORY

    # "No-good cuts": forbid each combination suggested before. If a previous meal used foods S,
    # at most |S| - 1 of them may be used together now, so the solver must change the combination.
    for combination in exclude:
        members = [used[i] for i, p in enumerate(candidates) if p.food.name in combination]
        if len(members) == len(combination):  # all still available
            prob += pulp.lpSum(members) <= len(members) - 1

    # Deviation from target, split into "under" and "over" (the standard trick to model |x| in LP)
    objective = []
    for macro, (w_under, w_over) in WEIGHTS.items():
        goal = getattr(target, macro)
        if goal <= 0:
            continue
        total = pulp.lpSum(getattr(p.food.per_serving, macro) * step * units[i] for i, p in enumerate(candidates))
        under = prob.add_variable(f"under_{macro}", 0)
        over = prob.add_variable(f"over_{macro}", 0)
        prob += total + under - over == goal
        objective += [w_under * under / goal, w_over * over / goal]

    prob += pulp.lpSum(objective) + PER_ITEM_PENALTY * pulp.lpSum(used.values())
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        return MealSuggestion([], ZERO_MACROS)  # e.g. every combination was already suggested

    chosen = {i: round(units[i].value() or 0) * step for i in units}
    items = [(p, chosen[i]) for i, p in enumerate(candidates) if chosen[i] > 0]
    totals = sum((p.food.per_serving.scale(n) for p, n in items), ZERO_MACROS)
    return MealSuggestion(items, totals)
