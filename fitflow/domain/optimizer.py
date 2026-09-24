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
"""

from dataclasses import dataclass

import pulp

from fitflow.domain.models import FoodCategory, Macros, Meal, PantryItem, ZERO_MACROS

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


@dataclass(frozen=True)
class MealSuggestion:
    items: list[tuple[PantryItem, int]]  # (pantry item, servings)
    totals: Macros


def suggest_meal(
    pantry: list[PantryItem],
    target: Macros,
    meal: Meal,
    disliked: frozenset[str] = frozenset(),
) -> MealSuggestion:
    candidates = [
        p for p in pantry
        if meal in p.food.meals and p.food.name not in disliked and p.max_servings > 0
    ]
    if not candidates or target.kcal <= 0:
        return MealSuggestion([], ZERO_MACROS)

    prob = pulp.LpProblem("meal", pulp.LpMinimize)
    servings = {
        i: prob.add_variable(f"servings_{i}", 0, p.max_servings, cat="Integer")
        for i, p in enumerate(candidates)
    }
    used = {i: prob.add_variable(f"used_{i}", cat="Binary") for i in servings}

    # Link the two variables: servings > 0  <=>  used = 1
    for i, p in enumerate(candidates):
        prob += servings[i] <= p.max_servings * used[i]
        prob += servings[i] >= used[i]

    prob += pulp.lpSum(used.values()) <= MAX_ITEMS
    for category in FoodCategory:
        in_category = [used[i] for i, p in enumerate(candidates) if p.food.category == category]
        if in_category:
            prob += pulp.lpSum(in_category) <= MAX_PER_CATEGORY

    # Deviation from target, split into "under" and "over" (the standard trick to model |x| in LP)
    objective = []
    for macro, (w_under, w_over) in WEIGHTS.items():
        goal = getattr(target, macro)
        if goal <= 0:
            continue
        total = pulp.lpSum(getattr(p.food.per_serving, macro) * servings[i] for i, p in enumerate(candidates))
        under = prob.add_variable(f"under_{macro}", 0)
        over = prob.add_variable(f"over_{macro}", 0)
        prob += total + under - over == goal
        objective += [w_under * under / goal, w_over * over / goal]

    prob += pulp.lpSum(objective) + PER_ITEM_PENALTY * pulp.lpSum(used.values())
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    chosen = {i: round(servings[i].value() or 0) for i in servings}
    items = [(p, chosen[i]) for i, p in enumerate(candidates) if chosen[i] > 0]
    totals = sum((p.food.per_serving.scale(n) for p, n in items), ZERO_MACROS)
    return MealSuggestion(items, totals)
