from fitflow.domain.models import Food, FoodCategory, Macros, Meal, PantryItem
from fitflow.domain.optimizer import MAX_ITEMS, suggest_meal

DINNER = frozenset({Meal.LUNCH, Meal.DINNER})
ANY = frozenset(Meal)

CHICKEN = Food("chicken breast", "100g", Macros(165, 31, 0, 3.6), FoodCategory.PROTEIN, DINNER)
EGG = Food("egg", "1 large", Macros(72, 6.3, 0.4, 4.8), FoodCategory.PROTEIN, ANY)
RICE = Food("white rice", "100g cooked", Macros(130, 2.7, 28, 0.3), FoodCategory.CARB, DINNER)
BREAD = Food("bread", "1 slice", Macros(80, 3, 15, 1), FoodCategory.CARB, ANY)
CEREAL = Food("cereal", "40g", Macros(150, 3, 33, 1), FoodCategory.CARB, frozenset({Meal.BREAKFAST}))
SALAD = Food("vegetable salad", "1 bowl", Macros(40, 2, 8, 0.3), FoodCategory.VEGETABLE, ANY)
OLIVE_OIL = Food("olive oil", "1 tbsp", Macros(120, 0, 0, 14), FoodCategory.FAT, ANY)
COTTAGE = Food("cottage 5%", "1/2 cup", Macros(110, 12, 4, 5), FoodCategory.DAIRY, ANY)

PANTRY = [
    PantryItem(CHICKEN, 3), PantryItem(EGG, 4), PantryItem(RICE, 3), PantryItem(BREAD, 3),
    PantryItem(CEREAL, 2), PantryItem(SALAD, 2), PantryItem(OLIVE_OIL, 2), PantryItem(COTTAGE, 2),
]


def names(suggestion) -> set[str]:
    return {p.food.name for p, _ in suggestion.items}


def test_hits_protein_without_blowing_calories():
    target = Macros(kcal=600, protein_g=50, carbs_g=50, fat_g=15)
    s = suggest_meal(PANTRY, target, Meal.DINNER)
    assert s.totals.protein_g >= 45
    assert s.totals.kcal <= 650


def test_respects_meal_type():
    s = suggest_meal(PANTRY, Macros(600, 30, 80, 15), Meal.DINNER)
    assert "cereal" not in names(s)


def test_respects_dislikes():
    s = suggest_meal(PANTRY, Macros(600, 50, 50, 15), Meal.DINNER, disliked=frozenset({"chicken breast"}))
    assert "chicken breast" not in names(s)


def test_respects_pantry_quantities_and_item_limit():
    s = suggest_meal(PANTRY, Macros(2000, 150, 200, 60), Meal.DINNER)
    assert len(s.items) <= MAX_ITEMS
    assert all(n <= p.max_servings for p, n in s.items)


def test_empty_pantry_returns_empty_suggestion():
    assert suggest_meal([], Macros(600, 50, 50, 15), Meal.DINNER).items == []


def test_nothing_left_to_eat_returns_empty_suggestion():
    assert suggest_meal(PANTRY, Macros(-100, 0, 0, 0), Meal.DINNER).items == []


def test_meal_is_inferred_from_hour():
    from fitflow.domain.optimizer import meal_for_hour
    assert meal_for_hour(8) == Meal.BREAKFAST
    assert meal_for_hour(13) == Meal.LUNCH
    assert meal_for_hour(20) == Meal.DINNER
    assert meal_for_hour(2) == Meal.DINNER  # late-night snack still "dinner-like"


def test_meal_target_splits_the_rest_of_the_day():
    from fitflow.domain.optimizer import meal_target
    daily = Macros(2000, 150, 200, 60)
    lunch = meal_target(Macros(1200, 90, 120, 36), daily, Meal.LUNCH)  # 3 meals left
    assert lunch.kcal == 400 and lunch.protein_g == 30


def test_meal_target_is_capped_to_a_reasonable_plate():
    from fitflow.domain.optimizer import MAX_MEAL_SHARE, meal_target
    daily = Macros(2000, 150, 200, 60)
    dinner = meal_target(daily, daily, Meal.DINNER)  # nothing eaten all day
    assert dinner.kcal == 2000 * MAX_MEAL_SHARE
    assert dinner.protein_g == 150 * MAX_MEAL_SHARE  # all macros shrink together


def test_different_suggestion_changes_the_combination():
    from fitflow.domain.optimizer import suggest_meal
    target = Macros(600, 50, 50, 15)
    first = suggest_meal(PANTRY, target, Meal.DINNER)
    second = suggest_meal(PANTRY, target, Meal.DINNER, exclude=[frozenset(names(first))])
    assert second.items and names(second) != names(first)


def test_no_more_alternatives_returns_empty():
    from fitflow.domain.optimizer import suggest_meal
    pantry = [PantryItem(CHICKEN, 3)]  # only one possible combination
    first = suggest_meal(pantry, Macros(600, 50, 50, 15), Meal.DINNER)
    assert suggest_meal(pantry, Macros(600, 50, 50, 15), Meal.DINNER, exclude=[frozenset(names(first))]).items == []


def test_fit_meal_uses_every_chosen_food_in_half_servings():
    from fitflow.domain.optimizer import fit_meal
    result = fit_meal([CHICKEN, RICE, SALAD], Macros(600, 50, 60, 15))
    assert names(result) == {"chicken breast", "white rice", "vegetable salad"}
    assert all((n * 2).is_integer() for _, n in result.items)       # multiples of 0.5
    assert result.totals.protein_g >= 45            # enough protein (extra protein is fine by design)
    assert abs(result.totals.kcal - 600) < 60       # calories on target
